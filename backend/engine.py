from datetime import date, timedelta

import pandas as pd

from backend.config import PRODUCTS, TODAY

# Only these pieces can ever appear in SQL. Values always go in as parameters.
METRICS = {
    "revenue": "ROUND(SUM(revenue), 2)",
    "quantity": "CAST(SUM(quantity) AS BIGINT)",
}
GROUPS = ("product", "category")
PERIODS = ("today", "yesterday", "this_week", "last_week", "this_month",
           "last_month", "last_30_days", "all")
CATEGORIES = {details[0] for details in PRODUCTS.values()}


def period_bounds(period: str, today: date = TODAY):
    """Start and end date (both inclusive) for a named period."""
    if period == "today":
        return today, today
    if period == "yesterday":
        d = today - timedelta(days=1)
        return d, d
    if period == "this_week":                      # Monday to today
        return today - timedelta(days=today.weekday()), today
    if period == "last_week":                      # previous Monday to Sunday
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
    raise ValueError(f"unsupported period: {period}")


def _check_metric(metric):
    if metric not in METRICS:
        raise ValueError(f"unsupported metric: {metric}")


def _where(period, product=None, category=None):
    start, end = period_bounds(period)
    where, params = ["date BETWEEN ? AND ?"], [start, end]
    if product is not None:
        if product not in PRODUCTS:
            raise ValueError(f"unknown product: {product}")
        where.append("product = ?")
        params.append(product)
    if category is not None:
        if category not in CATEGORIES:
            raise ValueError(f"unknown category: {category}")
        where.append("category = ?")
        params.append(category)
    return " AND ".join(where), params


def ranked(con, metric="revenue", group_by="product", period="last_30_days",
           limit=5, order="desc", product=None, category=None) -> pd.DataFrame:
    """Top (or bottom) products or categories. Columns: label, value."""
    _check_metric(metric)
    if group_by not in GROUPS:
        raise ValueError(f"unsupported group_by: {group_by}")
    if order not in ("asc", "desc"):
        raise ValueError(f"unsupported order: {order}")
    limit = max(1, min(int(limit), 20))
    where, params = _where(period, product, category)
    sql = (f"SELECT {group_by} AS label, {METRICS[metric]} AS value FROM sales "
           f"WHERE {where} GROUP BY {group_by} "
           f"ORDER BY value {order.upper()}, label LIMIT {limit}")
    return con.execute(sql, params).df()


def total(con, metric="revenue", period="last_30_days", product=None, category=None) -> float:
    _check_metric(metric)
    where, params = _where(period, product, category)
    row = con.execute(
        f"SELECT COALESCE({METRICS[metric]}, 0) FROM sales WHERE {where}", params).fetchone()
    return float(row[0])


def daily(con, metric="revenue", period="last_30_days", product=None, category=None) -> pd.DataFrame:
    """One row per day, for a trend chart. Columns: label (date), value."""
    _check_metric(metric)
    where, params = _where(period, product, category)
    sql = (f"SELECT CAST(date AS DATE) AS label, {METRICS[metric]} AS value FROM sales "
           f"WHERE {where} GROUP BY label ORDER BY label")
    return con.execute(sql, params).df()


def compare(con, metric="revenue", period_a="this_week", period_b="last_week",
            product=None, category=None) -> dict:
    a = total(con, metric, period_a, product, category)
    b = total(con, metric, period_b, product, category)
    change = a - b
    pct = None if b == 0 else round(change / b * 100, 1)
    return {"period_a": period_a, "value_a": a, "period_b": period_b,
            "value_b": b, "change": change, "pct_change": pct}


def low_stock(con) -> pd.DataFrame:
    """Products whose counted stock is below their reorder level."""
    return con.execute(
        "SELECT product, counted_stock, reorder_level FROM inventory "
        "WHERE counted_stock < reorder_level "
        "ORDER BY counted_stock - reorder_level, product").df()


def wastage(con, period="all", limit=5) -> pd.DataFrame:
    """Damaged quantity per product, from purchases. Columns: label, value."""
    start, end = period_bounds(period)
    limit = max(1, min(int(limit), 20))
    sql = ("SELECT product AS label, CAST(SUM(damaged_qty) AS BIGINT) AS value FROM purchases "
           "WHERE date BETWEEN ? AND ? GROUP BY product "
           f"ORDER BY value DESC, label LIMIT {limit}")
    return con.execute(sql, [start, end]).df()


def stock_gaps(con, only_gaps: bool = True) -> pd.DataFrame:
    """Stock Loss Detective.
    expected = opening + purchased - sold - damaged;  gap = counted - expected.
    A negative gap means fewer units than the records explain (a potential discrepancy)."""
    sql = """
    WITH s AS (SELECT product, CAST(SUM(quantity) AS BIGINT) AS sold
               FROM sales GROUP BY product),
         p AS (SELECT product, CAST(SUM(purchased_qty) AS BIGINT) AS bought,
                      CAST(SUM(damaged_qty) AS BIGINT) AS damaged
               FROM purchases GROUP BY product)
    SELECT product, opening_stock, purchased, sold, damaged, expected_stock,
           counted_stock, counted_stock - expected_stock AS gap
    FROM (
        SELECT i.product, i.opening_stock,
               COALESCE(p.bought, 0) AS purchased,
               COALESCE(s.sold, 0) AS sold,
               COALESCE(p.damaged, 0) AS damaged,
               i.opening_stock + COALESCE(p.bought, 0) - COALESCE(s.sold, 0)
                   - COALESCE(p.damaged, 0) AS expected_stock,
               i.counted_stock
        FROM inventory i
        LEFT JOIN s ON s.product = i.product
        LEFT JOIN p ON p.product = i.product
    )
    ORDER BY ABS(counted_stock - expected_stock) DESC, product
    """
    df = con.execute(sql).df()
    return df[df["gap"] != 0].reset_index(drop=True) if only_gaps else df