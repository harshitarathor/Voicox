
# tests/test_stock_detection.py

import pandas as pd
from backend.config import DATA_DIR, PRODUCTS


def test_planted_gaps_exist_in_data():
    # Read generated datasets
    sales = pd.read_csv(DATA_DIR / "sales.csv")
    purchases = pd.read_csv(DATA_DIR / "purchases.csv")
    inv = pd.read_csv(DATA_DIR / "inventory.csv")

    # Calculate total sales, purchases and damaged quantities
    sold = (
        sales.groupby("product")["quantity"]
        .sum()
        .reindex(PRODUCTS, fill_value=0)
    )

    bought = (
        purchases.groupby("product")["purchased_qty"]
        .sum()
        .reindex(PRODUCTS, fill_value=0)
    )

    dmg = (
        purchases.groupby("product")["damaged_qty"]
        .sum()
        .reindex(PRODUCTS, fill_value=0)
    )

    # Calculate expected stock
    inv["expected"] = (
        inv["opening_stock"]
        + inv["product"].map(bought)
        - inv["product"].map(sold)
        - inv["product"].map(dmg)
    )

    # Calculate stock discrepancy
    inv["gap"] = inv["counted_stock"] - inv["expected"]

    gaps = inv.set_index("product")["gap"]
    gaps = gaps[gaps != 0]

    # Verify exactly three discrepancies exist
    assert set(gaps.index) == {"Chawal", "Tel", "Doodh"}

    # Verify planted unexplained losses
    assert gaps["Tel"] == -8
    assert gaps["Doodh"] == -15

    # Verify missing Chawal sales record creates a negative gap
    assert gaps["Chawal"] < 0
