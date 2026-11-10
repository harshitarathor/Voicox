from datetime import date, timedelta

import duckdb
import pytest

from backend import engine
from backend.config import PRODUCTS, TODAY

P1, P2 = list(PRODUCTS)[:2]
C1, C2 = PRODUCTS[P1][0], PRODUCTS[P2][0]


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE TABLE sales(date DATE, product VARCHAR, category VARCHAR, "
              "quantity INTEGER, revenue DOUBLE)")
    c.execute("CREATE TABLE purchases(date DATE, product VARCHAR, "
              "purchased_qty INTEGER, damaged_qty INTEGER)")
    c.execute("CREATE TABLE inventory(product VARCHAR, opening_stock INTEGER, "
              "counted_stock INTEGER, reorder_level INTEGER)")

    yesterday = TODAY - timedelta(days=1)
    rows = [
        (TODAY, P1, C1, 10, 100.0),
        (yesterday, P1, C1, 5, 50.0),
        (TODAY, P2, C2, 2, 400.0),
    ]
    c.executemany("INSERT INTO sales VALUES (?, ?, ?, ?, ?)", rows)
    c.execute("INSERT INTO purchases VALUES (?, ?, 50, 5)",
              [TODAY - timedelta(days=3), P1])
    c.executemany("INSERT INTO inventory VALUES (?, ?, ?, ?)",
                  [(P1, 100, 5, 10),      # sold 15, bought 50, damaged 5 -> expected 130
                   (P2, 20, 18, 10)])     # sold 2 -> expected 18, matches count
    yield c
    c.close()


# ---------- periods ----------
def test_period_bounds():
    t = date(2026, 11, 4)  # a Wednesday
    assert engine.period_bounds("today", t) == (t, t)
    assert engine.period_bounds("yesterday", t) == (date(2026, 11, 3),) * 2
    assert engine.period_bounds("this_week", t) == (date(2026, 11, 2), t)
    assert engine.period_bounds("last_week", t) == (date(2026, 10, 26), date(2026, 11, 1))
    assert engine.period_bounds("this_month", t) == (date(2026, 11, 1), t)
    assert engine.period_bounds("last_month", t) == (date(2026, 10, 1), date(2026, 10, 31))
    assert engine.period_bounds("last_30_days", t) == (date(2026, 10, 6), t)


def test_unsupported_period_raises():
    with pytest.raises(ValueError):
        engine.period_bounds("next_year")


# ---------- totals ----------
def test_total_revenue(con):
    assert engine.total(con, "revenue", "last_30_days") == 550.0


def test_total_quantity(con):
    assert engine.total(con, "quantity", "last_30_days") == 17


def test_total_for_one_product(con):
    assert engine.total(con, "revenue", "last_30_days", product=P1) == 150.0


def test_total_with_no_data_is_zero(con):
    assert engine.total(con, "revenue", "last_month") == 0.0


# ---------- safety ----------
def test_unknown_product_raises(con):
    with pytest.raises(ValueError):
        engine.total(con, "revenue", "all", product="Laptop")


def test_unknown_category_raises(con):
    with pytest.raises(ValueError):
        engine.total(con, "revenue", "all", category="Electronics")


def test_unsupported_metric_raises(con):
    with pytest.raises(ValueError):
        engine.total(con, "revenue; DROP TABLE sales", "all")


def test_bad_group_by_raises(con):
    with pytest.raises(ValueError):
        engine.ranked(con, group_by="product; DROP TABLE sales")


def test_bad_order_raises(con):
    with pytest.raises(ValueError):
        engine.ranked(con, order="sideways")


# ---------- ranked ----------
def test_ranked_top_by_revenue(con):
    df = engine.ranked(con, "revenue", "product", "last_30_days", limit=5)
    assert list(df["label"]) == [P2, P1]
    assert list(df["value"]) == [400.0, 150.0]


def test_ranked_slow_moving_is_ascending(con):
    df = engine.ranked(con, "quantity", "product", "last_30_days", limit=1, order="asc")
    assert list(df["label"]) == [P2]       # sold only 2 units
    assert int(df["value"][0]) == 2


def test_ranked_limit_is_respected(con):
    assert len(engine.ranked(con, limit=1)) == 1


# ---------- daily and compare ----------
def test_daily_has_one_row_per_day(con):
    df = engine.daily(con, "revenue", "last_30_days")
    assert len(df) == 2
    assert list(df["value"]) == [50.0, 500.0]   # yesterday, then today


def test_compare_today_with_yesterday(con):
    r = engine.compare(con, "revenue", "today", "yesterday")
    assert r["value_a"] == 500.0
    assert r["value_b"] == 50.0
    assert r["change"] == 450.0
    assert r["pct_change"] == 900.0


def test_compare_with_zero_base_has_no_percentage(con):
    r = engine.compare(con, "revenue", "today", "last_month")
    assert r["value_b"] == 0.0
    assert r["pct_change"] is None


# ---------- inventory ----------
def test_low_stock_lists_only_items_below_reorder_level(con):
    df = engine.low_stock(con)
    assert list(df["product"]) == [P1]


def test_wastage(con):
    df = engine.wastage(con, "all")
    assert list(df["label"]) == [P1]
    assert int(df["value"][0]) == 5


# ---------- stock loss detective ----------
def test_stock_gaps_finds_the_planted_gap(con):
    df = engine.stock_gaps(con)
    assert list(df["product"]) == [P1]
    row = df.iloc[0]
    assert row["expected_stock"] == 130
    assert row["counted_stock"] == 5
    assert row["gap"] == -125


def test_stock_gaps_can_return_all_products(con):
    df = engine.stock_gaps(con, only_gaps=False)
    assert set(df["product"]) == {P1, P2}
    assert int(df[df["product"] == P2]["gap"].iloc[0]) == 0