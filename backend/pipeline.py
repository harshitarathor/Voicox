import duckdb
import pandas as pd

from backend.config import ALIASES, DATA_DIR, PRODUCTS

SALES_COLUMNS = ["txn_id", "date", "product", "quantity", "unit_price", "discount_pct"]
PURCHASE_COLUMNS = ["date", "product", "purchased_qty", "damaged_qty"]
INVENTORY_COLUMNS = ["product", "opening_stock", "counted_stock", "reorder_level"]
MAX_REJECTED_SHOWN = 50   # how many rejected rows the report lists for the UI

# Every spelling we know -> the standard product name (built once).
_LOOKUP = {name.casefold(): product
           for product, names in ALIASES.items()
           for name in (product, *names)}


# ---------- helpers ----------
def normalize_product(value):
    """'Rice', ' chawal ', 'चावल' -> 'Chawal'. Unknown or missing -> None."""
    if pd.isna(value):
        return None
    return _LOOKUP.get(str(value).strip().casefold())


def _require_columns(frame, columns, name):
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"{name} file is missing columns: {sorted(missing)}")


def _reject(df, ok, reason, rejected):
    """Keep rows where ok is True. Remember the others with their reason.
    Returns (kept_rows, number_rejected)."""
    bad = df[~ok]
    if len(bad):
        rejected.append(bad.assign(reason=reason))
    return df[ok].copy(), len(bad)


def _whole_positive(series, allow_zero=False):
    """True for numbers that are whole (no decimals) and > 0 (or >= 0)."""
    nums = pd.to_numeric(series, errors="coerce")
    limit_ok = nums >= 0 if allow_zero else nums > 0
    return nums.notna() & limit_ok & (nums % 1 == 0)


def _rejected_records(parts):
    """Rejected rows as a list of plain dicts, ready to show in the UI."""
    if not parts:
        return []
    rej = pd.concat(parts).sort_index().head(MAX_REJECTED_SHOWN)
    out = rej.astype(object)
    out = out.where(rej.notna(), "").astype(str)
    out.insert(0, "csv_line", [int(i) + 2 for i in rej.index])   # header is line 1
    return out.to_dict("records")


def _read_csv(name):
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run: python -m backend.data.generate_data")
    return pd.read_csv(path)


# ---------- sales ----------
def clean_sales(raw: pd.DataFrame):
    """Clean the raw sales export. Returns (clean_dataframe, report_dict)."""
    _require_columns(raw, SALES_COLUMNS, "sales")
    df = raw[SALES_COLUMNS].copy()
    report = {"rows_read": len(df)}
    rejected = []

    # 1. exact duplicate rows
    df, report["duplicates_removed"] = _reject(
        df, ~df.duplicated(), "duplicate row", rejected)

    # 2. missing or unreadable date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df, report["missing_date"] = _reject(
        df, df["date"].notna(), "missing or unreadable date", rejected)

    # 3. quantity: whole number, above zero
    df, report["invalid_quantity"] = _reject(
        df, _whole_positive(df["quantity"]),
        "invalid quantity (missing, zero, negative or decimal)", rejected)
    df["quantity"] = pd.to_numeric(df["quantity"]).astype(int)

    # 4. price: above zero
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df, report["invalid_price"] = _reject(
        df, df["unit_price"].notna() & (df["unit_price"] > 0),
        "invalid price (missing, zero or negative)", rejected)

    # 5. discount: blank means no discount; text or values outside 0-100 are rejected
    disc = pd.to_numeric(df["discount_pct"], errors="coerce")
    unreadable = disc.isna() & df["discount_pct"].notna()
    df, report["invalid_discount"] = _reject(
        df, ~unreadable & disc.fillna(0).between(0, 100),
        "invalid discount (must be 0 to 100)", rejected)
    df["discount_pct"] = pd.to_numeric(df["discount_pct"], errors="coerce").fillna(0)

    # 6. product: any known spelling is accepted and converted to the standard name
    standard = df["product"].map(normalize_product)
    df, report["unknown_product"] = _reject(
        df, standard.notna(), "unknown product", rejected)
    df["product"] = standard.loc[df.index]

    # 7. standard format
    df["date"] = df["date"].dt.normalize()
    df["category"] = df["product"].map(lambda p: PRODUCTS[p][0])
    df["revenue"] = (df["quantity"] * df["unit_price"] * (1 - df["discount_pct"] / 100)).round(2)

    df = df.sort_values(["date", "txn_id"]).reset_index(drop=True)
    report["rows_clean"] = len(df)
    report["rows_rejected"] = report["rows_read"] - report["rows_clean"]
    report["rejected_rows"] = _rejected_records(rejected)
    return df, report


# ---------- purchases ----------
def clean_purchases(raw: pd.DataFrame):
    """Validate deliveries. Returns (clean_dataframe, report_dict)."""
    _require_columns(raw, PURCHASE_COLUMNS, "purchases")
    df = raw[PURCHASE_COLUMNS].copy()
    report = {"rows_read": len(df)}
    rejected = []

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df, report["missing_date"] = _reject(
        df, df["date"].notna(), "missing or unreadable date", rejected)

    standard = df["product"].map(normalize_product)
    df, report["unknown_product"] = _reject(
        df, standard.notna(), "unknown product", rejected)
    df["product"] = standard.loc[df.index]

    df, report["invalid_purchased_qty"] = _reject(
        df, _whole_positive(df["purchased_qty"], allow_zero=True),
        "invalid purchased quantity", rejected)
    df["purchased_qty"] = pd.to_numeric(df["purchased_qty"]).astype(int)

    ok = _whole_positive(df["damaged_qty"], allow_zero=True)
    ok &= pd.to_numeric(df["damaged_qty"], errors="coerce") <= df["purchased_qty"]
    df, report["invalid_damaged_qty"] = _reject(
        df, ok, "invalid damaged quantity (negative, decimal or more than purchased)", rejected)
    df["damaged_qty"] = pd.to_numeric(df["damaged_qty"]).astype(int)

    df = df.sort_values(["date", "product"]).reset_index(drop=True)
    report["rows_clean"] = len(df)
    report["rows_rejected"] = report["rows_read"] - report["rows_clean"]
    report["rejected_rows"] = _rejected_records(rejected)
    return df, report


# ---------- inventory ----------
def clean_inventory(raw: pd.DataFrame):
    """Validate the stock count. Returns (clean_dataframe, report_dict)."""
    _require_columns(raw, INVENTORY_COLUMNS, "inventory")
    df = raw[INVENTORY_COLUMNS].copy()
    report = {"rows_read": len(df)}
    rejected = []

    standard = df["product"].map(normalize_product)
    df, report["unknown_product"] = _reject(
        df, standard.notna(), "unknown product", rejected)
    df["product"] = standard.loc[df.index]

    # a product listed twice would double-count its stock, so keep the first only
    df, report["duplicate_product"] = _reject(
        df, ~df["product"].duplicated(), "product listed more than once", rejected)

    ok = pd.Series(True, index=df.index)
    for col in ("opening_stock", "counted_stock", "reorder_level"):
        ok &= _whole_positive(df[col], allow_zero=True)
    df, report["invalid_stock_value"] = _reject(
        df, ok, "invalid stock value (negative, missing or decimal)", rejected)
    for col in ("opening_stock", "counted_stock", "reorder_level"):
        df[col] = pd.to_numeric(df[col]).astype(int)

    df = df.reset_index(drop=True)
    report["rows_clean"] = len(df)
    report["rows_rejected"] = report["rows_read"] - report["rows_clean"]
    report["rejected_rows"] = _rejected_records(rejected)
    return df, report


# ---------- load everything ----------
def load_all(db_path: str = ":memory:"):
    """Clean sales, purchases and inventory, then load them into DuckDB.
    Returns (connection, report). The report has the sales counts at the top level
    and the other two under report['purchases'] and report['inventory']."""
    sales, report = clean_sales(_read_csv("sales_raw.csv"))
    purchases, purchases_report = clean_purchases(_read_csv("purchases.csv"))
    inventory, inventory_report = clean_inventory(_read_csv("inventory.csv"))
    report["purchases"] = purchases_report
    report["inventory"] = inventory_report

    con = duckdb.connect(db_path)
    try:
        con.register("sales_df", sales)
        con.register("purchases_df", purchases)
        con.register("inventory_df", inventory)
        con.execute("CREATE OR REPLACE TABLE sales AS SELECT * FROM sales_df")
        con.execute("CREATE OR REPLACE TABLE purchases AS SELECT * FROM purchases_df")
        con.execute("CREATE OR REPLACE TABLE inventory AS SELECT * FROM inventory_df")
    except Exception:
        con.close()
        raise
    return con, report


def summary_line(report: dict) -> str:
    """One line for the UI and README, e.g. '892 rows loaded, 13 rejected'."""
    return f"{report['rows_clean']:,} rows loaded, {report['rows_rejected']} rejected"