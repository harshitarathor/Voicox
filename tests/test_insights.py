from datetime import date, timedelta

import duckdb
import pytest

from backend import insights
from backend.config import DATA_DIR, PRODUCTS

P1, P2, P3 = list(PRODUCTS)[:3]
START = date(2026, 10, 1)


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE TABLE sales(date DATE, product VARCHAR, category VARCHAR, "
              "quantity INTEGER, revenue DOUBLE)")
    c.execute("CREATE TABLE purchases(date DATE, product VARCHAR, "
              "purchased_qty INTEGER, damaged_qty INTEGER)")
    c.execute("CREATE TABLE inventory(product VARCHAR, opening_stock INTEGER, "
              "counted_stock INTEGER, reorder_level INTEGER)")

    rows = []
    for i in range(10):
        if i == 4:                      # the shop has no sales record on this day
            continue
        d = START + timedelta(days=i)
        rows += [(d, P1, PRODUCTS[P1][0], 10, 100.0),
                 (d, P2, PRODUCTS[P2][0], 5, 50.0),
                 (d, P3, PRODUCTS[P3][0], 3, 30.0)]
    c.executemany("INSERT INTO sales VALUES (?, ?, ?, ?, ?)", rows)

    c.executemany("INSERT INTO purchases VALUES (?, ?, ?, ?)",
                  [(START, P1, 100, 2), (START, P2, 50, 0), (START, P3, 20, 0)])

    # P1: expected 200+100-90-2 = 208, counted 198 -> gap -10 (one missed day of 10 units)
    # P2: expected 100+50-45 = 105, counted 105 -> no gap
    # P3: expected 50+20-27 = 43, counted 43 -> no gap, but below its reorder level
    c.executemany("INSERT INTO inventory VALUES (?, ?, ?, ?)",
                  [(P1, 200, 198, 10), (P2, 100, 105, 10), (P3, 50, 43, 60)])
    yield c
    c.close()


def test_low_stock_alerts(con):
    alerts = insights.low_stock_alerts(con)
    assert [a["product"] for a in alerts] == [P3]
    assert alerts[0]["shortfall"] == 17
    assert P3 in alerts[0]["message"]


def test_stock_gap_alerts_find_only_the_gap(con):
    alerts = insights.stock_gap_alerts(con)
    assert [a["product"] for a in alerts] == [P1]
    assert alerts[0]["gap"] == -10


def test_alert_wording_never_accuses(con):
    text = insights.speak_stock_gaps(con).lower()
    assert "potential" in text
    assert "chori" not in text and "theft" not in text


def test_spoken_summary_when_nothing_to_report(con):
    con.execute("UPDATE inventory SET counted_stock = 208 WHERE product = ?", [P1])
    assert "match" in insights.speak_stock_gaps(con)


def test_explain_gap_ranks_missing_sales_day_first(con):
    r = insights.explain_gap(con, P1)
    assert r["gap"] == -10
    assert r["causes"][0]["rule"] == "no_sales_day"
    assert r["causes"][0]["score"] >= 0.9
    assert "1 din" in r["causes"][0]["headline"]


def test_causes_are_sorted_by_score(con):
    scores = [c["score"] for c in insights.explain_gap(con, P1)["causes"]]
    assert scores == sorted(scores, reverse=True)


def test_recount_is_always_the_last_resort(con):
    r = insights.explain_gap(con, P1)
    assert r["causes"][-1]["rule"] == "recount"


def test_no_gap_means_no_causes(con):
    r = insights.explain_gap(con, P2)
    assert r["gap"] == 0
    assert r["causes"] == []


def test_high_damage_is_flagged(con):
    con.execute("UPDATE purchases SET damaged_qty = 30 WHERE product = ?", [P1])
    rules = [c["rule"] for c in insights.explain_gap(con, P1)["causes"]]
    assert "high_damage" in rules


def test_normal_damage_is_not_flagged(con):
    rules = [c["rule"] for c in insights.explain_gap(con, P1)["causes"]]
    assert "high_damage" not in rules


def test_extra_stock_points_to_missing_purchase(con):
    con.execute("UPDATE inventory SET counted_stock = 115 WHERE product = ?", [P2])
    rules = [c["rule"] for c in insights.explain_gap(con, P2)["causes"]]
    assert "unrecorded_purchase" in rules
    assert "no_sales_day" not in rules


def test_unknown_product_raises(con):
    with pytest.raises(ValueError):
        insights.explain_gap(con, "Laptop")


def test_every_explanation_carries_the_disclaimer(con):
    assert "nishkarsh nahi" in insights.explain_gap(con, P1)["spoken"]


# ---- real generated data: is the planted cause actually found? ----
@pytest.mark.skipif(
    not all((DATA_DIR / f"{t}.csv").exists() for t in ("sales", "purchases", "inventory")),
    reason="generated data files not found")
def test_real_data_chawal_cause_is_the_missing_sales_day():
    c = duckdb.connect(":memory:")
    for t in ("sales", "purchases", "inventory"):
        c.execute(f"CREATE VIEW {t} AS SELECT * FROM read_csv_auto('{(DATA_DIR / (t + '.csv')).as_posix()}')")
    r = insights.explain_gap(c, "Chawal")
    assert r["gap"] < 0
    assert r["causes"][0]["rule"] == "no_sales_day"