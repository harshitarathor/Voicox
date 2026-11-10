import pandas as pd
import pytest

from backend.config import DATA_DIR, PRODUCTS
from backend.pipeline import (clean_inventory, clean_purchases, clean_sales,
                              load_all, normalize_product, summary_line)


def sales_frame(**overrides):
    """One valid sales row; override any column to make it invalid."""
    row = {"txn_id": 1, "date": "2026-10-01", "product": "Chawal",
           "quantity": 5, "unit_price": 60, "discount_pct": 0}
    row.update(overrides)
    return pd.DataFrame([row])


# ---------- the planted problems in the real generated file ----------
def test_planted_problems_are_found():
    raw = pd.read_csv(DATA_DIR / "sales_raw.csv")
    clean, report = clean_sales(raw)
    assert report["duplicates_removed"] == 5
    assert report["missing_date"] == 3
    assert report["invalid_quantity"] == 3
    assert report["invalid_price"] == 0
    assert report["invalid_discount"] == 0
    assert report["unknown_product"] == 2
    assert report["rows_rejected"] == 13
    assert report["rows_clean"] == len(raw) - 13


def test_clean_data_equals_recorded_sales():
    raw = pd.read_csv(DATA_DIR / "sales_raw.csv")
    clean, _ = clean_sales(raw)
    expected = pd.read_csv(DATA_DIR / "sales.csv")
    assert len(clean) == len(expected)
    assert clean["quantity"].sum() == expected["quantity"].sum()
    assert abs(clean["revenue"].sum() - expected["revenue"].sum()) < 0.01


def test_rejected_rows_are_listed_with_reasons():
    raw = pd.read_csv(DATA_DIR / "sales_raw.csv")
    _, report = clean_sales(raw)
    rows = report["rejected_rows"]
    assert len(rows) == 13
    assert all(r["reason"] and r["csv_line"] >= 2 for r in rows)
    assert {r["reason"] for r in rows} == {
        "duplicate row", "missing or unreadable date",
        "invalid quantity (missing, zero, negative or decimal)", "unknown product"}


# ---------- product aliases ----------
def test_normalize_product():
    assert normalize_product("Rice") == "Chawal"
    assert normalize_product("  chawal ") == "Chawal"
    assert normalize_product("चावल") == "Chawal"
    assert normalize_product("MILK") == "Doodh"
    assert normalize_product("Chawl") is None          # typos are not guessed
    assert normalize_product(None) is None
    assert normalize_product(float("nan")) is None


def test_aliases_become_standard_names_in_clean_data():
    raw = pd.concat([sales_frame(txn_id=1, product="Rice"),
                     sales_frame(txn_id=2, product="चावल"),
                     sales_frame(txn_id=3, product="milk")], ignore_index=True)
    clean, report = clean_sales(raw)
    assert report["unknown_product"] == 0
    assert list(clean["product"]) == ["Chawal", "Chawal", "Doodh"]
    assert list(clean["category"]) == ["Grocery", "Grocery", "Dairy"]


# ---------- sales validation rules ----------
@pytest.mark.parametrize("column, value, report_key", [
    ("quantity", 2.5, "invalid_quantity"),
    ("quantity", 0, "invalid_quantity"),
    ("quantity", -1, "invalid_quantity"),
    ("quantity", None, "invalid_quantity"),
    ("unit_price", 0, "invalid_price"),
    ("unit_price", -5, "invalid_price"),
    ("unit_price", None, "invalid_price"),
    ("discount_pct", -5, "invalid_discount"),
    ("discount_pct", 150, "invalid_discount"),
    ("discount_pct", "ten", "invalid_discount"),
    ("date", "", "missing_date"),
    ("product", "Laptop", "unknown_product"),
])
def test_each_bad_value_is_rejected_and_counted(column, value, report_key):
    clean, report = clean_sales(sales_frame(**{column: value}))
    assert len(clean) == 0
    assert report[report_key] == 1
    assert report["rows_rejected"] == 1


def test_blank_discount_means_no_discount():
    clean, report = clean_sales(sales_frame(discount_pct=None))
    assert report["rows_rejected"] == 0
    assert clean.loc[0, "revenue"] == 300.0


def test_small_dirty_file():
    raw = pd.DataFrame({
        "txn_id":       [1, 1, 2, 3, 4, 5, 6],
        "date":         ["2026-10-01", "2026-10-01", "2026-10-02", "", "2026-10-03", "2026-10-03", "2026-10-04"],
        "product":      ["Chawal", "Chawal", "Atta", "Atta", "Laptop", "Doodh", "  doodh "],
        "quantity":     [5, 5, -1, 3, 2, 2, 4],
        "unit_price":   [60, 60, 45, 45, 50, 0, 30],
        "discount_pct": [0, 0, 0, 0, 0, 0, 10],
    })
    clean, report = clean_sales(raw)
    assert report["rows_read"] == 7
    assert report["duplicates_removed"] == 1
    assert report["missing_date"] == 1
    assert report["invalid_quantity"] == 1
    assert report["invalid_price"] == 1
    assert report["unknown_product"] == 1
    assert report["rows_clean"] == 2
    assert set(clean["product"]) == {"Chawal", "Doodh"}
    assert clean.loc[clean["product"] == "Doodh", "revenue"].iloc[0] == 108.0


def test_missing_column_raises():
    with pytest.raises(ValueError):
        clean_sales(pd.DataFrame({"txn_id": [1]}))


# ---------- purchases and inventory ----------
def test_real_purchases_and_inventory_are_all_valid():
    p, pr = clean_purchases(pd.read_csv(DATA_DIR / "purchases.csv"))
    i, ir = clean_inventory(pd.read_csv(DATA_DIR / "inventory.csv"))
    assert pr["rows_rejected"] == 0 and ir["rows_rejected"] == 0
    assert len(i) == len(PRODUCTS)


def test_bad_purchases_are_rejected():
    raw = pd.DataFrame({
        "date":          ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "", "2026-10-06"],
        "product":       ["Chawal", "Chawal", "Chawal", "Rice", "Atta", "Laptop"],
        "purchased_qty": [50, -5, 40, 30, 20, 10],
        "damaged_qty":   [2, 0, 41, 1, 0, 0],
    })
    clean, report = clean_purchases(raw)
    assert report["invalid_purchased_qty"] == 1      # -5
    assert report["invalid_damaged_qty"] == 1        # 41 damaged of 40 bought
    assert report["missing_date"] == 1
    assert report["unknown_product"] == 1
    assert list(clean["product"]) == ["Chawal", "Chawal"]   # 'Rice' became Chawal


def test_bad_inventory_is_rejected():
    raw = pd.DataFrame({
        "product":       ["Chawal", "chawal", "Atta", "Tel", "Laptop"],
        "opening_stock": [150, 150, 150, -1, 150],
        "counted_stock": [100, 100, 100, 100, 100],
        "reorder_level": [30, 30, 30, 30, 30],
    })
    clean, report = clean_inventory(raw)
    assert report["duplicate_product"] == 1
    assert report["invalid_stock_value"] == 1
    assert report["unknown_product"] == 1
    assert list(clean["product"]) == ["Chawal", "Atta"]


# ---------- loading ----------
def test_load_all_creates_tables():
    con, report = load_all()
    assert con.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == report["rows_clean"]
    assert con.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == len(PRODUCTS)
    assert con.execute("SELECT COUNT(*) FROM purchases").fetchone()[0] > 0
    assert report["purchases"]["rows_rejected"] == 0
    assert report["inventory"]["rows_rejected"] == 0
    assert "rejected" in summary_line(report)


def test_missing_data_file_gives_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.pipeline.DATA_DIR", tmp_path)
    with pytest.raises(FileNotFoundError, match="generate_data"):
        load_all()
        