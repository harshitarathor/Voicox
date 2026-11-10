"""FastAPI app: text question -> extract -> validate -> DuckDB -> answer.

The model never writes SQL and never calculates numbers. Every number here
comes from engine.py or insights.py. Voice (Gnani) is added later as extra
routes that feed a transcript into the same /ask pipeline.
"""
import json
import logging
import threading
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from starlette.concurrency import run_in_threadpool

from backend import engine, gnani, insights, phrases, pipeline
from backend.config import PROJECT_ROOT, TODAY
from backend.extractor import extract, refusal
from backend.schemas import StructuredQuery
from backend.validator import validate

log = logging.getLogger("voicox")
FRONTEND = PROJECT_ROOT / "frontend" / "index.html"
BENCHMARK = PROJECT_ROOT / "benchmark" / "results.json"

# ---------------------------------------------------------------- database
_state = {"con": None, "report": None}
_load_lock = threading.Lock()      # only one request loads the data
_db_lock = threading.Lock()        # one query at a time on the shared connection


def get_con():
    """The shared DuckDB connection, loaded on first use."""
    if _state["con"] is None:
        with _load_lock:
            if _state["con"] is None:
                _state["con"], _state["report"] = pipeline.load_all()
    return _state["con"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_con()                                   # fail early if the data cannot load
    yield
    if _state["con"] is not None:
        _state["con"].close()
        _state["con"] = _state["report"] = None


app = FastAPI(title="Voicox", lifespan=lifespan)

# ---------------------------------------------------------------- wording
# "Pichle mahine sabse zyada ..."  (before a verb)
PERIOD_EVENT = {"today": "Aaj", "yesterday": "Kal", "this_week": "Is hafte",
                "last_week": "Pichle hafte", "this_month": "Is mahine",
                "last_month": "Pichle mahine", "last_30_days": "Pichle 30 din mein",
                "all": "Ab tak"}
# "Pichle mahine ki bikri ..."     (before a noun)
PERIOD_KI = {"today": "Aaj ki", "yesterday": "Kal ki", "this_week": "Is hafte ki",
             "last_week": "Pichle hafte ki", "this_month": "Is mahine ki",
             "last_month": "Pichle mahine ki", "last_30_days": "Pichle 30 din ki",
             "all": "Ab tak ki"}


def _commas(n) -> str:
    """420000 -> 4,20,000 (Indian grouping, for the screen)."""
    n = int(round(float(n)))
    sign, s = ("-" if n < 0 else ""), str(abs(n))
    if len(s) > 3:
        head, tail, parts = s[:-3], s[-3:], []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return sign + s


def _say(n) -> str:
    """420000 -> '4 lakh 20 hazaar' (for the voice; check how Timbre reads it)."""
    n = int(round(float(n)))
    if n < 0:
        return "minus " + _say(-n)
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    hazaar, n = divmod(n, 1000)
    parts = [f"{v} {w}" for v, w in ((crore, "crore"), (lakh, "lakh"), (hazaar, "hazaar")) if v]
    if n or not parts:
        parts.append(str(n))
    return " ".join(parts)


def _spoken_amount(x, metric: str) -> str:
    return f"{_say(x)} rupaye" if metric == "revenue" else f"{_say(x)} unit"


def _shown_amount(x, metric: str) -> str:
    return f"₹{_commas(x)}" if metric == "revenue" else f"{_commas(x)} unit"


def _spoken_date(label: str) -> str:
    d = date.fromisoformat(str(label)[:10])
    return f"{d.day} {d:%B}"


def _label(x) -> str:
    """'2026-10-02 00:00:00' -> '2026-10-02' (a date needs no time of day)."""
    s = str(x)
    return s[:10] if len(s) == 19 and s[10] == " " and s.endswith("00:00:00") else s


def _rows(df) -> list:
    return [{"label": _label(r.label), "value": float(r.value)} for r in df.itertuples()]


def _chart(rows, title, kind="bar") -> Optional[dict]:
    if not rows:
        return None
    return {"type": kind, "title": title,
            "x": [r["label"] for r in rows], "y": [r["value"] for r in rows]}


def describe(q: StructuredQuery) -> str:
    """The interpreted query in one readable line (Trust Mode)."""
    bits = [q.intent, f"metric={q.metric}", f"period={q.period}"]
    if q.compare_period:
        bits.append(f"compare_with={q.compare_period}")
    if q.intent == "ranked":
        bits += [f"by={q.group_by}", f"limit={q.limit}", f"order={q.order}"]
    if q.product:
        bits.append(f"product={q.product}")
    if q.category:
        bits.append(f"category={q.category}")
    return " | ".join(bits)


# ---------------------------------------------------------------- run one query
def _has_rows(con, period, product=None, category=None) -> bool:
    where, params = engine._where(period, product, category)
    return con.execute(f"SELECT COUNT(*) FROM sales WHERE {where}", params).fetchone()[0] > 0


def run_query(con, q: StructuredQuery, lang: str = "hn") -> dict:
    """Answer one validated query. `lang` (hn / en / hi) only changes the words, never a number."""
    lang = phrases.norm(lang)
    out = {"intent": q.intent, "spoken": "", "numbers": {}, "table": [],
           "chart": None, "causes": [], "alerts": [], "disclaimer": None}
    metric = q.metric
    when, when_ki = phrases.ev(lang, q.period), phrases.ki(lang, q.period)
    amt = lambda x: phrases.amount(x, metric, lang)
    no_data = phrases.s("no_data", lang, when, when_ki)

    if q.intent == "total":
        who = phrases.nm(lang, q.product or q.category) if (q.product or q.category) else None
        if not _has_rows(con, q.period, q.product, q.category):   # no records is not "zero sales"
            out["spoken"] = no_data
            return out
        value = engine.total(con, metric, q.period, q.product, q.category)
        out["numbers"] = {"value": value, "metric": metric, "period": q.period,
                          "display": _shown_amount(value, metric)}
        if metric == "quantity":
            out["spoken"] = phrases.s("total_qty", lang, when, who, amt(value))
        elif who:
            out["spoken"] = phrases.s("total_rev_who", lang, when, who, amt(value))
        else:
            out["spoken"] = phrases.s("total_rev", lang, when_ki, amt(value))
        rows = _rows(engine.daily(con, metric, q.period, q.product, q.category))
        if len(rows) > 1:
            out["chart"] = _chart(rows, phrases.s("t_daily", lang, who, metric), "line")

    elif q.intent == "ranked":
        rows = _rows(engine.ranked(con, metric, q.group_by, q.period, q.limit, q.order,
                                   q.product, q.category))
        out["table"] = rows
        more = q.order == "desc"
        if not rows:
            out["spoken"] = no_data
        elif len(rows) == 1 or q.limit == 1:
            top = rows[0]
            key = "rank_one_qty" if metric == "quantity" else "rank_one_rev"
            out["spoken"] = phrases.s(key, lang, when, more, phrases.nm(lang, top["label"]), amt(top["value"]))
        else:
            items = ", ".join(f"{phrases.nm(lang, r['label'])} {amt(r['value'])}" for r in rows[:3])
            out["spoken"] = phrases.s("rank_many", lang, when, more, min(len(rows), 3), items)
        out["chart"] = _chart(rows, phrases.s("t_rank", lang, more, metric, when))

    elif q.intent == "trend":
        rows = _rows(engine.daily(con, metric, q.period, q.product, q.category))
        out["table"] = rows
        if not rows:
            out["spoken"] = no_data
        else:
            total = sum(r["value"] for r in rows)
            peak = max(rows, key=lambda r: r["value"])
            out["spoken"] = phrases.s("trend", lang, when_ki, amt(total), phrases.day_text(peak["label"], lang))
            out["chart"] = _chart(rows, phrases.s("t_daily", lang, None, metric), "line")

    elif q.intent == "compare":
        a, b = q.period, q.compare_period
        if not (_has_rows(con, a, q.product, q.category) and _has_rows(con, b, q.product, q.category)):
            missing = a if not _has_rows(con, a, q.product, q.category) else b
            out["spoken"] = phrases.s("no_data", lang, phrases.ev(lang, missing), phrases.ki(lang, missing))
            return out
        r = engine.compare(con, metric, a, b, q.product, q.category)
        out["numbers"] = r
        word, kind = phrases.direction(lang, r["change"])
        pct = phrases.s("pct", lang, abs(r["pct_change"])) if r["pct_change"] is not None else ""
        out["spoken"] = phrases.s("compare", lang, phrases.ev(lang, a), amt(r["value_a"]),
                                  phrases.ev(lang, b), amt(r["value_b"]), amt(abs(r["change"])), pct,
                                  "same" if (kind == "same" and lang == "en") else word)
        out["chart"] = _chart([{"label": phrases.ev(lang, a), "value": r["value_a"]},
                               {"label": phrases.ev(lang, b), "value": r["value_b"]}],
                              phrases.s("t_compare", lang, metric))

    elif q.intent == "low_stock":
        alerts = insights.low_stock_alerts(con, lang)
        if q.product:
            alerts = [a for a in alerts if a["product"] == q.product]
        out["alerts"] = alerts
        out["spoken"] = insights.speak_alerts(alerts, phrases.s("low_empty", lang), lang=lang)
        if q.product and not alerts:                       # not low: give its numbers instead of "nothing is low"
            row = con.execute("SELECT counted_stock, reorder_level FROM inventory WHERE product = ?",
                              [q.product]).fetchone()
            if row:
                out["spoken"] = phrases.s("stock_ok", lang, phrases.nm(lang, q.product),
                                          phrases.say(row[0], lang), phrases.say(row[1], lang))
        out["chart"] = _chart([{"label": a["product"], "value": a["counted_stock"]} for a in alerts],
                              phrases.s("t_low", lang))

    elif q.intent == "wastage":
        rows = _rows(engine.wastage(con, q.period, q.limit))
        out["table"] = rows
        if rows and rows[0]["value"] > 0:
            out["spoken"] = phrases.s("wastage_top", lang, when, phrases.nm(lang, rows[0]["label"]),
                                      phrases.say(rows[0]["value"], lang))
        else:
            out["spoken"] = phrases.s("wastage_none", lang)
        out["chart"] = _chart(rows, phrases.s("t_damaged", lang))

    elif q.intent == "stock_gap":
        alerts = insights.stock_gap_alerts(con, lang)
        if q.product:
            alerts = [a for a in alerts if a["product"] == q.product]
        out["alerts"] = alerts
        if alerts:
            out["spoken"] = insights.speak_alerts(alerts, "", lang=lang)
        elif q.product:
            out["spoken"] = phrases.s("gap_none_one", lang, phrases.nm(lang, q.product))
        else:
            out["spoken"] = phrases.s("gap_none_all", lang)
        out["chart"] = _chart([{"label": a["product"], "value": a["gap"]} for a in alerts],
                              phrases.s("t_gap", lang))

    elif q.intent == "explain_gap":
        r = insights.explain_gap(con, q.product, lang)
        out["numbers"] = {k: r[k] for k in ("product", "gap", "expected_stock", "counted_stock")}
        out["causes"] = r["causes"]
        out["spoken"] = r["spoken"]
        out["disclaimer"] = r["disclaimer"]

    else:
        raise ValueError(f"Unsupported intent: {q.intent}")

    return out


def _execute(q: StructuredQuery, lang: str = "hn") -> dict:
    with _db_lock:
        return run_query(get_con(), q, lang)


# ---------------------------------------------------------------- API
class AskRequest(BaseModel):
    text: Optional[str] = Field(default=None, max_length=1000)   # typed or transcribed question
    query: Optional[dict] = None          # a query the user has just confirmed
    confirmed: bool = False
    lang: Optional[str] = None            # en, hi or hn (Hinglish, the default): the language of the answer

    @model_validator(mode="after")
    def not_both(self):
        if self.text and self.text.strip() and self.query is not None:
            raise ValueError("Send either text or query, not both.")
        return self


def _reply(status, transcript="", query=None, message="", result=None, http=200, lang="hn"):
    body = {"status": status, "transcript": transcript, "message": message,
            "voice": phrases.to_voice(message or (result or {}).get("spoken", ""), lang),   # for the speaker
            "query": query.model_dump() if query is not None else None,
            "query_text": describe(query) if query is not None else "",
            "today": str(TODAY), "result": result}
    return JSONResponse(body, status_code=http) if http != 200 else body


@app.post("/ask")
def ask(req: AskRequest):
    transcript = (req.text or "").strip()
    lang = phrases.norm(req.lang)
    msg = lambda key, *a: phrases.s(key, lang, *a)

    # 1. text -> structured query (or take the one the user confirmed)
    if req.query is not None:
        raw = req.query
    else:
        if not transcript:
            return _reply("reject", message=msg("m_empty"), lang=lang)
        raw = extract(transcript)
        if raw is None:
            why = refusal(transcript)           # a clear "I cannot answer that", never a guessed number
            message = msg(*why) if why and why[1] else msg(why[0]) if why else msg("m_no_understand")
            return _reply("reject", transcript, message=message, lang=lang)

    # 2. check it against the whitelist (also for a query the user "confirmed")
    verdict = validate(raw, lang)
    if verdict.status in ("reject", "clarify"):
        return _reply(verdict.status, transcript, verdict.query, verdict.message, lang=lang)
    q = verdict.query

    if q.intent == "explain_gap" and not q.product:
        return _reply("clarify", transcript, q, msg("m_which_product"), lang=lang)
    if verdict.status == "confirm" and not req.confirmed:
        return _reply("confirm", transcript, q, verdict.message, lang=lang)

    # 3. DuckDB computes the answer
    try:
        result = _execute(q, lang)
    except ValueError:
        return _reply("clarify", transcript, q, msg("m_unsupported"), lang=lang)
    except Exception:
        log.exception("query failed: %s", q)
        return _reply("error", transcript, q, msg("m_failed"), http=500, lang=lang)
    return _reply("ok", transcript, q, result=result, lang=lang)


# ---------------------------------------------------------------- voice (Gnani)
MAX_AUDIO_BYTES = 5 * 1024 * 1024        # 30 s of WAV is well under this


def _gnani_message(e: "gnani.GnaniError", lang: str) -> str:
    """The voice-service problem, worded in the answer's language (Hinglish text as a fallback)."""
    key = f"g_{e.code}"
    return phrases.s(key, lang) if key in phrases.S else e.message


@app.get("/voice-status")
def voice_status():
    """The page hides the mic when no Gnani key is set."""
    return {"configured": gnani.configured()}


@app.post("/ask-audio")
async def ask_audio(request: Request, lang: str = "hn"):
    """Body = the recording itself (Content-Type audio/wav). Prisma writes it out as
    text, then the text goes through exactly the same steps as a typed question."""
    lang = phrases.norm(lang)
    audio = await request.body()
    if not audio:
        return _reply("reject", message=phrases.s("m_audio_empty", lang), lang=lang)
    if len(audio) > MAX_AUDIO_BYTES:
        return _reply("reject", message=phrases.s("m_audio_long", lang), http=413, lang=lang)
    content_type = request.headers.get("content-type", "audio/wav").split(";")[0].strip()
    try:
        text = await run_in_threadpool(gnani.transcribe, audio, content_type)
    except gnani.GnaniError as e:
        return _reply("error", message=_gnani_message(e, lang), http=e.http, lang=lang)
    if not text:
        return _reply("reject", message=phrases.s("m_audio_unclear", lang), lang=lang)
    return await run_in_threadpool(ask, AskRequest(text=text[:1000], lang=lang))


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=600)    # the answer's spoken line
    lang: Optional[str] = None                         # en, hi or hn: picks the voice language


@app.post("/speak")
def speak(req: SpeakRequest):
    try:
        wav = gnani.synthesize(req.text, phrases.norm(req.lang))
    except gnani.GnaniError as e:
        return JSONResponse({"status": "error", "message": _gnani_message(e, phrases.norm(req.lang))},
                            status_code=e.http)
    return Response(wav, media_type="audio/wav")


def _fixed(intent: str, lang: str = "hn"):
    lang = phrases.norm(lang)
    q = StructuredQuery(intent=intent)
    try:
        return _reply("ok", query=q, result=_execute(q, lang), lang=lang)
    except Exception:
        log.exception("%s failed", intent)
        return _reply("error", message=phrases.s("m_failed_short", lang), http=500, lang=lang)


@app.get("/stock-gaps")
def stock_gaps(lang: str = "hn"):
    return _fixed("stock_gap", lang)


@app.get("/low-stock")
def low_stock(lang: str = "hn"):
    return _fixed("low_stock", lang)


@app.get("/data-report")
def data_report():
    """What the cleaning step removed, with reasons (for a Data Quality panel)."""
    get_con()
    return {"report": _state["report"], "summary": pipeline.summary_line(_state["report"])}


# ---------------------------------------------------------------- home screen + reliability
def week_change(rows: list, today: date) -> Optional[float]:
    """% change of the last 7 days against the 7 days before, from real daily rows.
    None when either week has no sales, so the page shows no arrow instead of a guess."""
    last = prev = 0.0
    n_last = n_prev = 0
    for r in rows:
        age = (today - date.fromisoformat(r["label"][:10])).days
        if 0 <= age <= 6:
            last, n_last = last + r["value"], n_last + 1
        elif 7 <= age <= 13:
            prev, n_prev = prev + r["value"], n_prev + 1
    if n_last < 7 or n_prev < 7 or prev <= 0:
        return None
    return round((last - prev) / prev * 100, 1)


def build_summary(con) -> dict:
    """Everything the Home tiles show. Every number comes from engine.py / insights.py."""
    revenue = engine.total(con, "revenue", "last_30_days")
    units = engine.total(con, "quantity", "last_30_days")
    daily = _rows(engine.daily(con, "revenue", "last_30_days"))
    daily_units = _rows(engine.daily(con, "quantity", "last_30_days"))
    top = _rows(engine.ranked(con, "revenue", "product", "last_30_days", 3, "desc"))
    gaps = insights.stock_gap_alerts(con)
    low = insights.low_stock_alerts(con)
    stock = con.execute("SELECT counted_stock, reorder_level FROM inventory").fetchall()
    out = sum(1 for counted, _ in stock if counted <= 0)
    low_n = sum(1 for counted, reorder in stock if 0 < counted < reorder)
    return {
        "today": str(TODAY),
        "revenue_30d": revenue, "units_30d": units,
        "trend": {"x": [r["label"] for r in daily], "y": [r["value"] for r in daily]},
        "units_trend": {"x": [r["label"] for r in daily_units], "y": [r["value"] for r in daily_units]},
        "revenue_week_change": week_change(daily, TODAY),
        "units_week_change": week_change(daily_units, TODAY),
        "top": top,
        "mismatch_count": len(gaps), "low_count": len(low),
        "health": {"healthy": len(stock) - low_n - out, "low": low_n, "out": out,
                   "total": len(stock)},
        "insight": ({"text": gaps[0]["message"], "product": gaps[0]["product"]}
                    if gaps else None),            # gaps are sorted, the largest first
    }


@app.get("/summary")
def summary():
    try:
        with _db_lock:
            return build_summary(get_con())
    except Exception:
        log.exception("summary failed")
        return JSONResponse({"status": "error", "message": "Kuch gadbad ho gayi."}, status_code=500)


def build_sales_overview(con) -> dict:
    """Sales page: daily revenue plus the best and slowest sellers, all from engine.py."""
    daily = _rows(engine.daily(con, "revenue", "last_30_days"))
    return {
        "today": str(TODAY),
        "daily": {"x": [r["label"] for r in daily], "y": [r["value"] for r in daily]},
        "top": _rows(engine.ranked(con, "revenue", "product", "last_30_days", 5, "desc")),
        "slow": _rows(engine.ranked(con, "revenue", "product", "last_30_days", 5, "asc")),
    }


def build_stock_overview(con) -> dict:
    """Stock page: every product with its counted stock and reorder level."""
    rows = con.execute(
        "SELECT product, counted_stock, reorder_level FROM inventory ORDER BY product").fetchall()
    items = [{"product": p, "counted": float(c), "reorder_level": float(r),
              "status": "out" if c <= 0 else "low" if c < r else "ok"} for p, c, r in rows]
    return {"today": str(TODAY), "items": items}


def _guarded(build, name):
    try:
        with _db_lock:
            return build(get_con())
    except Exception:
        log.exception("%s failed", name)
        return JSONResponse({"status": "error", "message": "Kuch gadbad ho gayi."}, status_code=500)


@app.get("/sales-overview")
def sales_overview():
    return _guarded(build_sales_overview, "sales-overview")


@app.get("/stock-overview")
def stock_overview():
    return _guarded(build_stock_overview, "stock-overview")


@app.get("/benchmark")
def benchmark():
    """Measured results written by benchmark/run_benchmark.py. Nothing is invented:
    until that file exists the page says so and the Reliability tab stays hidden."""
    if not BENCHMARK.exists():
        return {"available": False}
    try:
        return {"available": True, **json.loads(BENCHMARK.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        log.exception("benchmark results unreadable")
        return {"available": False}


@app.get("/health")
def health():
    return {"ok": True, "today": str(TODAY)}


@app.get("/ready")
def ready():
    """Can the database be loaded and queried?"""
    try:
        with _db_lock:
            counts = {t: get_con().execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in ("sales", "purchases", "inventory")}
        return {"ready": all(counts.values()), "rows": counts}
    except Exception:
        log.exception("not ready")
        return JSONResponse({"ready": False}, status_code=503)


if FRONTEND.parent.is_dir():                      # css/, js/ and assets/ next to index.html
    app.mount("/static", StaticFiles(directory=FRONTEND.parent), name="static")


@app.get("/")
def home():
    if FRONTEND.exists():
        return FileResponse(FRONTEND)
    return JSONResponse({"message": "Voicox API is running. Open /docs to try it. "
                                    "frontend/index.html has not been created yet."})