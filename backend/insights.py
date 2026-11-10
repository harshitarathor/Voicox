"""Alerts, spoken sentences, and the "Why?" cause rules.

Everything here is a fixed rule over data already in DuckDB. No model is involved.
Causes are leads to check, never verdicts.
"""
import math
from datetime import timedelta
from statistics import median

from backend import engine, phrases

# Tunable thresholds
DAMAGE_MIN_RATIO = 0.05      # damage below 5% of purchases is never "high"
DAMAGE_VS_OTHERS = 2.0       # high = more than 2x the median of other products

ZERO_SALE_DAY_CHANCE = 0.01   # below this, a product with no sales on a day looks suspicious

DISCLAIMER = phrases.s("disclaimer", "hn")        # the Hinglish text; other languages come from phrases.py


def _n(x) -> str:
    x = float(x)
    return str(int(x)) if x.is_integer() else f"{x:.1f}"


# ---------------------------------------------------------------- alerts
def low_stock_alerts(con, lang: str = "hn") -> list[dict]:
    df = engine.low_stock(con)
    alerts = []
    for r in df.itertuples():
        short = int(r.reorder_level - r.counted_stock)
        alerts.append({
            "product": r.product,
            "counted_stock": int(r.counted_stock),
            "reorder_level": int(r.reorder_level),
            "shortfall": short,
            "message": phrases.s("alert_low", lang, phrases.nm(lang, r.product),
                                 int(r.counted_stock), int(r.reorder_level)),
        })
    return alerts


def stock_gap_alerts(con, lang: str = "hn") -> list[dict]:
    """One alert per product whose counted stock differs from expected stock."""
    df = engine.stock_gaps(con)
    alerts = []
    for r in df.itertuples():
        gap = int(r.gap)
        p, e, c = phrases.nm(lang, r.product), int(r.expected_stock), int(r.counted_stock)
        msg = (phrases.s("alert_short", lang, p, abs(gap), e, c) if gap < 0
               else phrases.s("alert_over", lang, p, gap, e, c))
        alerts.append({"product": r.product, "gap": gap,
                       "expected_stock": int(r.expected_stock),
                       "counted_stock": int(r.counted_stock), "message": msg})
    return alerts


def speak_alerts(alerts: list[dict], empty: str, max_items: int = 3, lang: str = "hn") -> str:
    """Join the top alerts into one short sentence block for text-to-speech."""
    if not alerts:
        return empty
    parts = [a["message"] for a in alerts[:max_items]]
    extra = len(alerts) - max_items
    if extra > 0:
        parts.append(phrases.s("alerts_more", lang, extra))
    return " ".join(parts)


def speak_low_stock(con, lang: str = "hn") -> str:
    return speak_alerts(low_stock_alerts(con, lang), phrases.s("low_empty", lang), lang=lang)


def speak_stock_gaps(con, lang: str = "hn") -> str:
    return speak_alerts(stock_gap_alerts(con, lang), phrases.s("gap_none_all", lang), lang=lang)


# ---------------------------------------------------------------- "Why?" rules
def _missing_sales_days(con) -> list:
    """Days between the first and last sale on which the shop has no sales rows at all."""
    row = con.execute("SELECT MIN(CAST(date AS DATE)), MAX(CAST(date AS DATE)) FROM sales").fetchone()
    if row[0] is None:
        return []
    lo, hi = row
    present = {d for (d,) in con.execute("SELECT DISTINCT CAST(date AS DATE) FROM sales").fetchall()}
    days, d = [], lo
    while d <= hi:
        if d not in present:
            days.append(d)
        d += timedelta(days=1)
    return days


def _product_missing_days(con, product) -> list:
    """Days when the shop sold other things but this product has no sales row."""
    all_days = [d for (d,) in con.execute(
        "SELECT DISTINCT CAST(date AS DATE) FROM sales ORDER BY 1").fetchall()]
    mine = {d for (d,) in con.execute(
        "SELECT DISTINCT CAST(date AS DATE) FROM sales WHERE product = ?", [product]).fetchall()}
    return [d for d in all_days if d not in mine]


def _rule_no_sales_days(con, product, gap, lang="hn"):
    """Counted < expected, and some days have no sales record (whole shop or this product)."""
    if gap >= 0:
        return None
    days = _missing_sales_days(con)
    whole_shop = bool(days)
    if not days:
        days = _product_missing_days(con, product)
    if not days:
        return None
    sold, active = con.execute(
        "SELECT COALESCE(SUM(quantity), 0), COUNT(DISTINCT CAST(date AS DATE)) "
        "FROM sales WHERE product = ?", [product]).fetchone()
    avg_daily = float(sold) / active if active else 0.0
    # A slow seller often has a day with no sale. Blame missing days only when a
    # zero-sale day is unlikely for this product (under 1% chance on a normal day).
    if not whole_shop and math.exp(-avg_daily) >= ZERO_SALE_DAY_CHANCE:
        return None
    est = avg_daily * len(days)
    need = abs(gap)
    ratio = min(est, need) / max(est, need) if max(est, need) > 0 else 0.0
    shown = ", ".join(phrases.day_text(d, lang, short=True) for d in days[:3]) + (" ..." if len(days) > 3 else "")
    pn = phrases.nm(lang, product)
    return {
        "rule": "no_sales_day",
        "score": round(0.4 + 0.6 * ratio, 2),
        "headline": (phrases.s("r_nosales_whole", lang, len(days), shown) if whole_shop
                     else phrases.s("r_nosales_one", lang, len(days), pn, shown)),
        "detail": phrases.s("r_nosales_detail", lang, pn, _n(avg_daily), _n(est), need),
        "check_next": phrases.s("r_nosales_check", lang),
    }


def _rule_high_damage(con, product, gap, lang="hn"):
    """This product's damage rate is unusually high compared with other products."""
    df = con.execute(
        "SELECT product, CAST(SUM(damaged_qty) AS DOUBLE) AS dmg, "
        "CAST(SUM(purchased_qty) AS DOUBLE) AS bought FROM purchases GROUP BY product").df()
    df = df[df["bought"] > 0]
    mine = df[df["product"] == product]
    if mine.empty:
        return None
    ratio = float(mine["dmg"].iloc[0] / mine["bought"].iloc[0])
    rest = df[df["product"] != product]
    others = (rest["dmg"] / rest["bought"]).tolist()
    med = median(others) if others else 0.0
    threshold = max(DAMAGE_VS_OTHERS * med, DAMAGE_MIN_RATIO)
    if ratio <= threshold:
        return None
    dmg_units = int(mine["dmg"].iloc[0])
    return {
        "rule": "high_damage",
        "score": round(min(0.7, 0.3 + 0.1 * (ratio / threshold)), 2),
        "headline": phrases.s("r_damage_head", lang, f"{ratio * 100:.0f}"),
        "detail": phrases.s("r_damage_detail", lang, phrases.nm(lang, product), dmg_units,
                            f"{ratio * 100:.0f}", f"{med * 100:.0f}"),
        "check_next": phrases.s("r_damage_check", lang),
    }


def _rule_unrecorded_purchase(con, product, gap, lang="hn"):
    """Counted > expected: more stock than the records explain."""
    if gap <= 0:
        return None
    return {
        "rule": "unrecorded_purchase",
        "score": 0.5,
        "headline": phrases.s("r_unrec_head", lang),
        "detail": phrases.s("r_unrec_detail", lang, gap),
        "check_next": phrases.s("r_unrec_check", lang),
    }


def _rule_recount(con, product, gap, lang="hn"):
    """Always last: a counting slip is the cheapest thing to rule out."""
    return {
        "rule": "recount",
        "score": 0.2,
        "headline": phrases.s("r_recount_head", lang),
        "detail": phrases.s("r_recount_detail", lang),
        "check_next": phrases.s("r_recount_check", lang),
    }


RULES = (_rule_no_sales_days, _rule_high_damage, _rule_unrecorded_purchase, _rule_recount)


def explain_gap(con, product: str, lang: str = "hn") -> dict:
    """Ranked possible causes for one product's stock gap."""
    df = engine.stock_gaps(con, only_gaps=False)
    row = df[df["product"] == product]
    if row.empty:
        raise ValueError(f"unknown product: {product}")
    row = row.iloc[0]
    gap = int(row["gap"])
    base = {"product": product, "gap": gap,
            "expected_stock": int(row["expected_stock"]),
            "counted_stock": int(row["counted_stock"]),
            "disclaimer": phrases.s("disclaimer", lang)}

    if gap == 0:
        return {**base, "causes": [],
                "spoken": phrases.s("why_none", lang, phrases.nm(lang, product))}

    causes = [c for c in (rule(con, product, gap, lang) for rule in RULES) if c]
    causes.sort(key=lambda c: c["score"], reverse=True)

    top = causes[0]
    spoken = phrases.s("why_main", lang, phrases.nm(lang, product), abs(gap), gap < 0,
                       top["headline"], top["check_next"], base["disclaimer"])
    return {**base, "causes": causes, "spoken": spoken}