"""Voicox benchmark: how often does the app hear, understand and answer correctly?

Run from the project folder:
    python benchmark/run_benchmark.py              # uses recorded audio when it exists (Gnani credits only for new files)
    python benchmark/run_benchmark.py --no-gnani   # never calls Gnani: uses saved transcripts, else the typed question
    python benchmark/run_benchmark.py --text-only  # ignores audio completely (free)

What is measured, for each of the 30 questions in benchmark/questions.csv:
  speech   the text Prisma heard is at least 80% similar to what was said (only for recorded audio)
  query    the app turned the question into the right structured query (intent, metric, period, product)
  answer   the number or list in the answer equals the figure computed straight from the raw CSV files,
           by code in this file that does not use the app's own engine

Every transcript from Gnani is saved in benchmark/transcripts.json, so re-running never pays twice.
Results go to benchmark/results.json (the Reliability page reads it) and benchmark/results.md.
"""
import argparse
import csv
import difflib
import hashlib
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BENCH = ROOT / "benchmark"
DATA = ROOT / "backend" / "data"
LANG_OF = {"hinglish": "hn", "noisy": "hn", "hindi": "hi", "english": "en"}   # the answer language asked for
LABEL_OF = {"hinglish": "Hinglish", "hindi": "Hindi", "english": "English", "noisy": "Noisy"}
AUDIO_EXT = (".wav", ".m4a", ".mp3", ".ogg", ".flac", ".aac")
SPEECH_OK = 0.80
STOP_CODES = {"auth", "credit", "not_configured"}      # Gnani problems that make more calls pointless


# ------------------------------------------------------------ the truth, from the raw CSV files
def _bounds(period, today):
    if period == "today":
        return today, today
    if period == "yesterday":
        return today - timedelta(days=1), today - timedelta(days=1)
    if period == "this_week":
        return today - timedelta(days=today.weekday()), today
    if period == "last_week":
        start = today - timedelta(days=today.weekday() + 7)
        return start, start + timedelta(days=6)
    if period == "this_month":
        return today.replace(day=1), today
    if period == "last_month":
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    if period == "last_30_days":
        return today - timedelta(days=29), today
    if period == "all":
        return date(2000, 1, 1), today
    raise ValueError(period)


class Truth:
    """Figures computed with plain pandas from sales.csv, purchases.csv and inventory.csv."""

    def __init__(self, today):
        import pandas as pd
        self.today = today
        self.sales = pd.read_csv(DATA / "sales.csv", parse_dates=["date"])
        self.buy = pd.read_csv(DATA / "purchases.csv", parse_dates=["date"])
        self.inv = pd.read_csv(DATA / "inventory.csv")

    def _sales(self, period, product=None):
        a, b = _bounds(period, self.today)
        s = self.sales
        s = s[(s["date"].dt.date >= a) & (s["date"].dt.date <= b)]
        return s if product is None else s[s["product"] == product]

    def total(self, metric, period, product=None):
        col = "revenue" if metric == "revenue" else "quantity"
        return float(self._sales(period, product)[col].sum())

    def top(self, metric, period, asc=False):
        """The set of winning labels (a set, so a tie is not unfair), and the winning value."""
        col = "revenue" if metric == "revenue" else "quantity"
        g = self._sales(period).groupby("product")[col].sum()
        best = g.min() if asc else g.max()
        return set(g[g == best].index), float(best)

    def low(self):
        i = self.inv
        return set(i[i["counted_stock"] < i["reorder_level"]]["product"])

    def gaps(self):
        sold = self.sales.groupby("product")["quantity"].sum()
        bought = self.buy.groupby("product")["purchased_qty"].sum()
        dmg = self.buy.groupby("product")["damaged_qty"].sum()
        out = {}
        for _, r in self.inv.iterrows():
            p = r["product"]
            exp = int(r["opening_stock"]) + int(bought.get(p, 0)) - int(sold.get(p, 0)) - int(dmg.get(p, 0))
            gap = int(r["counted_stock"]) - exp
            if gap != 0:
                out[p] = gap
        return out

    def gap_of(self, product):
        return self.gaps().get(product, 0)

    def missing_days(self, product):
        """Days between the first and last sale on which this product has no sales at all."""
        s = self.sales
        days = set(s["date"].dt.date)
        have = set(s[s["product"] == product]["date"].dt.date)
        first, last = min(days), max(days)
        return sorted(d for d in (first + timedelta(n) for n in range((last - first).days + 1))
                      if d in days and d not in have)

    def wastage_top(self):
        g = self.buy.groupby("product")["damaged_qty"].sum()
        return set(g[g == g.max()].index)

    def stock_row(self, product):
        r = self.inv[self.inv["product"] == product].iloc[0]
        return int(r["counted_stock"]), int(r["reorder_level"])


# ------------------------------------------------------------ what each check expects
def expected_query(check):
    """The structured query a correct app must produce for this check, as {field: value}."""
    k, *a = check.split(":")
    if k == "top":
        e = {"intent": "ranked", "metric": a[0], "period": a[1], "limit": 1}
        e["order"] = "asc" if len(a) > 2 else "desc"
        return e
    if k == "total":
        e = {"intent": "total", "metric": a[0], "period": a[1]}
        if len(a) > 2:
            e["product"] = a[2]
        return e
    if k == "compare":
        return {"intent": "compare", "metric": a[0], "period": a[1], "compare_period": a[2]}
    if k == "stock":
        return {"intent": "low_stock", "product": a[0]}
    if k == "low":
        return {"intent": "low_stock"}
    if k == "gaps":
        return {"intent": "stock_gap"}
    if k == "why":
        return {"intent": "explain_gap", "product": a[0]}
    if k == "wastage":
        return {"intent": "wastage"}
    raise ValueError(f"unknown check: {check}")


def query_problem(check, got):
    """None when the query is right, else a short description of the difference."""
    want = expected_query(check)
    got = got or {}
    diffs = [f"{f} = {got.get(f)} (expected {v})" for f, v in want.items() if got.get(f) != v]
    if "product" not in want and got.get("product"):
        diffs.append(f"product = {got.get('product')} (expected none)")
    return "understood: " + "; ".join(diffs) if diffs else None


def answer_problem(check, d, truth):
    """None when the answer's figures equal the truth, else a short description."""
    r = d.get("result") or {}
    k, *a = check.split(":")
    close = lambda x, y: x is not None and abs(float(x) - float(y)) <= 0.51

    if k == "top":
        labels, best = truth.top(a[0], a[1], asc=len(a) > 2)
        rows = r.get("table") or []
        if not rows:
            return "no ranking returned"
        if rows[0]["label"] not in labels or not close(rows[0]["value"], best):
            return f"top was {rows[0]['label']} {rows[0]['value']}, expected {'/'.join(sorted(labels))} {best:g}"
    elif k == "total":
        want = truth.total(a[0], a[1], a[2] if len(a) > 2 else None)
        got = (r.get("numbers") or {}).get("value")
        if not close(got, want):
            return f"total was {got}, expected {want:g}"
    elif k == "compare":
        n = r.get("numbers") or {}
        wa, wb = truth.total(a[0], a[1]), truth.total(a[0], a[2])
        if not (close(n.get("value_a"), wa) and close(n.get("value_b"), wb)):
            return f"values were {n.get('value_a')} and {n.get('value_b')}, expected {wa:g} and {wb:g}"
    elif k == "stock":
        counted, reorder = truth.stock_row(a[0])
        alerts = [x for x in r.get("alerts") or [] if x.get("product") == a[0]]
        if counted < reorder:
            if not alerts or alerts[0].get("counted_stock") != counted:
                return f"low-stock alert missing or wrong (counted {counted}, reorder {reorder})"
        elif not re.search(rf"(?<!\d){counted}(?!\d)", r.get("spoken", "")):
            return f"answer does not state the counted stock {counted}"
    elif k == "low":
        got = {x["product"] for x in r.get("alerts") or []}
        if got != truth.low():
            return f"low-stock list was {sorted(got)}, expected {sorted(truth.low())}"
    elif k == "gaps":
        got = {x.get("product"): x.get("gap") for x in r.get("alerts") or []}
        if got != truth.gaps():
            return f"gaps were {got}, expected {truth.gaps()}"
    elif k == "why":
        n = r.get("numbers") or {}
        want = truth.gap_of(a[0])
        if n.get("gap") != want:
            return f"gap was {n.get('gap')}, expected {want}"
        if not r.get("causes"):
            return "no possible causes listed"
        if not r.get("disclaimer"):
            return "the 'possible causes, not accusations' note is missing"
        one_day = truth.missing_days(a[0])           # a product that sells every day except one, with stock missing
        if want < 0 and len(one_day) == 1 and r["causes"][0].get("rule") != "no_sales_day":
            return f"top cause was {r['causes'][0].get('rule')}, expected no_sales_day (no sales on {one_day[0]})"
    elif k == "wastage":
        labels = truth.wastage_top()
        rows = r.get("table") or []
        if not rows or rows[0]["label"] not in labels:
            return f"most damaged was {rows[0]['label'] if rows else None}, expected {'/'.join(sorted(labels))}"
    return None


# ------------------------------------------------------------ speech
def _norm(s):
    return " ".join(re.sub(r"[^\w\s]", " ", (s or "").lower()).split())


def similarity(heard, question, roman):
    """0..1. Compares with the Roman wording when Prisma answered in Roman letters (it normally does)."""
    ref = question if re.search(r"[ऀ-ॿ]", heard or "") or not roman else roman
    return difflib.SequenceMatcher(None, _norm(heard), _norm(ref)).ratio()


def find_audio(qid, group):
    for ext in AUDIO_EXT:
        p = BENCH / "audio" / group / f"{qid}{ext}"
        if p.exists():
            return p
    return None


CONTENT_TYPES = {".wav": "audio/wav", ".m4a": "audio/mp4", ".mp3": "audio/mpeg",
                 ".ogg": "audio/ogg", ".flac": "audio/flac", ".aac": "audio/aac"}


def hear(path, cache, allow_gnani, state, transcribe=None):
    """Transcript for one audio file: from the saved file when possible, else from Gnani.
    Returns (text or None, note). None means 'not measured'."""
    key = f"{path.parent.name}/{path.name}"
    data = path.read_bytes()
    sha = hashlib.sha1(data).hexdigest()
    hit = cache.get(key)
    if hit and hit.get("sha1") == sha:
        return hit["text"], ""
    if not allow_gnani or state.get("stopped"):
        return None, state.get("stopped") or "not transcribed yet (no Gnani call made)"
    if transcribe is None:
        from backend import gnani
        transcribe = gnani.transcribe
    from backend import gnani as _g
    if state.get("calls"):
        time.sleep(1.0)                                  # one request at a time, gently
    state["calls"] = state.get("calls", 0) + 1
    try:
        text = transcribe(data, CONTENT_TYPES.get(path.suffix.lower(), "audio/wav"))
    except _g.GnaniError as e:
        if e.code in STOP_CODES:
            state["stopped"] = f"Gnani stopped the run ({e.code}); the rest were not transcribed"
            return None, state["stopped"]
        if e.code == "bad_audio":
            return "", ""                                # Gnani could not read it: counts as not heard
        return None, f"Gnani busy or unavailable ({e.code})"
    cache[key] = {"sha1": sha, "text": text}
    return text, ""


# ------------------------------------------------------------ the run
def load_questions():
    with open(BENCH / "questions.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def run(text_only=False, no_gnani=False, write=True, transcribe=None, client=None):
    """Run every question and return the results dict (and write the files unless write=False)."""
    from backend.config import TODAY
    truth = Truth(TODAY)
    questions = load_questions()

    cache_file = BENCH / "transcripts.json"
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
    state = {}

    own_client = client is None
    if own_client:
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        client.__enter__()                                # starts the app, loads the data
    try:
        rows = []
        for q in questions:
            lang = LANG_OF[q["group"]]
            heard, source, note, sim = None, "typed", "", None
            path = None if text_only else find_audio(q["id"], q["group"])
            if path is not None:
                heard, note = hear(path, cache, not no_gnani, state, transcribe)
                if heard is not None:
                    source = "audio"
                    sim = similarity(heard, q["question"], q["roman"])
            text = heard if source == "audio" and heard else q["question"]

            d = client.post("/ask", json={"text": text, "lang": lang}).json()
            if d.get("status") == "confirm" and d.get("query"):          # the owner would tap "yes"
                d = client.post("/ask", json={"query": d["query"], "confirmed": True, "lang": lang}).json()

            problem = None
            if d.get("status") != "ok":
                problem = f"app said: {d.get('message') or d.get('status')}"
                q_ok = a_ok = False
            else:
                qp = query_problem(q["check"], d.get("query"))
                q_ok = qp is None
                ap = qp or answer_problem(q["check"], d, truth)
                a_ok = ap is None
                problem = ap
            rows.append({"id": q["id"], "group": q["group"], "question": q["question"], "source": source,
                         "heard": heard if source == "audio" else None, "similarity": sim,
                         "query_ok": q_ok, "answer_ok": a_ok, "problem": problem, "note": note})
    finally:
        if own_client:
            client.__exit__(None, None, None)

    if write and cache:
        cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    n = len(rows)
    heard_rows = [r for r in rows if r["source"] == "audio"]
    speech = (sum(r["similarity"] >= SPEECH_OK for r in heard_rows) / len(heard_rows)) if heard_rows else None
    by_language = {}
    for g in ("hinglish", "hindi", "english", "noisy"):
        grp = [r for r in rows if r["group"] == g]
        if grp:
            by_language[LABEL_OF[g]] = round(sum(r["answer_ok"] for r in grp) / len(grp), 4)

    failures = []
    for r in rows:
        if r["answer_ok"]:
            continue
        why = r["problem"] or "wrong answer"
        if r["source"] == "audio" and r["similarity"] < SPEECH_OK:
            why = f"heard only {r['similarity']:.0%} of the words; {why}"
        failures.append({"question": r["question"], "heard": r["heard"] if r["source"] == "audio" else "(typed)",
                         "problem": why})

    results = {
        "n_questions": n,
        "n_audio": len(heard_rows),
        "speech_accuracy": None if speech is None else round(speech, 4),
        "query_accuracy": round(sum(r["query_ok"] for r in rows) / n, 4),
        "answer_accuracy": round(sum(r["answer_ok"] for r in rows) / n, 4),
        "by_language": by_language,
        "failures": failures,
        "measured_on": date.today().isoformat(),
        "method": "Speech = Prisma transcript at least 80% like the spoken question (recorded files only). "
                  "Query = intent, metric, period and product all right. Answer = the figures equal those "
                  "computed directly from the raw CSV files. Questions without a recording are tested as typed text.",
        "audio_notes": sorted({r["note"] for r in rows if r["note"]}),
    }
    if write:
        (BENCH / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        (BENCH / "results.md").write_text(render_md(results, rows), encoding="utf-8")
    results["_rows"] = rows
    return results


def render_md(res, rows):
    pc = lambda x: "not measured (no recordings)" if x is None else f"{x:.0%}"
    out = [f"# Voicox benchmark ({res['measured_on']})", "",
           f"{res['n_questions']} questions, {res['n_audio']} of them spoken into a microphone "
           f"(the rest were typed).", "",
           "| Measure | Result |", "|---|---|",
           f"| Speech understood (Gnani Prisma) | {pc(res['speech_accuracy'])} |",
           f"| Question turned into the right query | {pc(res['query_accuracy'])} |",
           f"| Answer equals the raw-data figure | {pc(res['answer_accuracy'])} |", "",
           "## By language", "", "| Language | Correct answers |", "|---|---|"]
    out += [f"| {k} | {v:.0%} |" for k, v in res["by_language"].items()]
    out += ["", "## Every question", "", "| # | Group | Question | Input | Heard | Result |", "|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['id']} | {r['group']} | {r['question']} | {r['source']} | {r['heard'] or ''} | "
                   f"{'correct' if r['answer_ok'] else 'WRONG: ' + (r['problem'] or '')} |")
    out += ["", "## How this was measured", "", res["method"], ""]
    if res["audio_notes"]:
        out += ["Notes: " + "; ".join(res["audio_notes"]), ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Voicox benchmark")
    ap.add_argument("--text-only", action="store_true", help="ignore recordings, test typed questions only (free)")
    ap.add_argument("--no-gnani", action="store_true", help="never call Gnani: use saved transcripts only")
    a = ap.parse_args()
    res = run(text_only=a.text_only, no_gnani=a.no_gnani)
    pc = lambda x: "-" if x is None else f"{x:.0%}"
    print(f"{res['n_questions']} questions ({res['n_audio']} spoken)")
    print(f"  speech  {pc(res['speech_accuracy'])}\n  query   {pc(res['query_accuracy'])}\n  answer  {pc(res['answer_accuracy'])}")
    for k, v in res["by_language"].items():
        print(f"  {k:<9}{v:.0%}")
    for f in res["failures"]:
        print(f"  WRONG: {f['question']} -> {f['problem']}")
    for note in res["audio_notes"]:
        print("  note:", note)
    print("Written: benchmark/results.json and benchmark/results.md")


if __name__ == "__main__":
    main()
