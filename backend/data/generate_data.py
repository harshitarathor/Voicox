import numpy as np
import pandas as pd

from backend.config import DATA_DIR, PRODUCTS, TODAY

rng = np.random.default_rng(42)
DAYS = pd.date_range(end=pd.Timestamp(TODAY), periods=90)
OPENING = 150

# ---------- 0. check config ----------
assert PRODUCTS, "PRODUCTS cannot be empty"
for _name, _details in PRODUCTS.items():
    assert len(_details) == 3, f"{_name}: expected (category, price, demand)"
    assert _details[1] > 0 and _details[2] > 0, f"{_name}: invalid price or demand"

required_products = {"Tel", "Doodh", "Dahi", "Chawal", "Daal", "Sabun"}
missing_products = required_products - set(PRODUCTS)
assert not missing_products, f"Missing required products: {missing_products}"

# ---------- 1. TRUE sales (what really happened) ----------
rows = []
for d in DAYS:
    for product, (category, price, demand) in PRODUCTS.items():
        qty = int(rng.poisson(demand))
        if qty == 0:
            continue
        rows.append({
            "date": d.strftime("%Y-%m-%d"), "product": product, "category": category,
            "quantity": qty, "unit_price": price,
            "discount_pct": int(rng.choice([0, 0, 0, 5, 10])),
        })
full_sales = pd.DataFrame(rows)
full_sales.insert(0, "txn_id", range(1, len(full_sales) + 1))
full_sales["revenue"] = (full_sales.quantity * full_sales.unit_price
                         * (1 - full_sales.discount_pct / 100)).round(2)

# ---------- 2. purchases (weekly delivery, with damaged goods) ----------
HIGH_DAMAGE = {"Doodh", "Dahi"}
prows = []
for d in DAYS[::7]:
    for product, (_, _, demand) in PRODUCTS.items():
        purchased = int(round(demand * 7 * rng.uniform(0.9, 1.1)))
        damaged = int(rng.integers(3, 7)) if product in HIGH_DAMAGE else int(rng.choice([0, 0, 0, 1, 2]))
        prows.append({"date": d.strftime("%Y-%m-%d"), "product": product,
                      "purchased_qty": purchased, "damaged_qty": damaged})
purchases = pd.DataFrame(prows)

# ---------- 3. physical counts = reality (computed from TRUE sales) ----------
sold_true = full_sales.groupby("product")["quantity"].sum().reindex(list(PRODUCTS), fill_value=0)
bought = purchases.groupby("product")["purchased_qty"].sum().reindex(list(PRODUCTS), fill_value=0)
damaged_tot = purchases.groupby("product")["damaged_qty"].sum().reindex(list(PRODUCTS), fill_value=0)

inv = pd.DataFrame({"product": list(PRODUCTS)})
inv["opening_stock"] = OPENING
inv["counted_stock"] = (inv.opening_stock + inv["product"].map(bought)
                        - inv["product"].map(sold_true) - inv["product"].map(damaged_tot))

UNEXPLAINED = {"Tel": -8, "Doodh": -15}          # losses with no data cause, on purpose
for p, delta in UNEXPLAINED.items():
    inv.loc[inv["product"] == p, "counted_stock"] += delta
assert (inv.counted_stock >= 30).all(), "a count fell below 30; raise OPENING"

inv["reorder_level"] = 30
PLANTED_LOW = ["Daal", "Sabun"]
for p in PLANTED_LOW:
    cnt = int(inv.loc[inv["product"] == p, "counted_stock"].iloc[0])
    inv.loc[inv["product"] == p, "reorder_level"] = cnt + 15

# ---------- 4. records MISS one day of Chawal sales (the explainable cause) ----------
MISSING_DAY = (pd.Timestamp(TODAY) - pd.Timedelta(days=20)).strftime("%Y-%m-%d")
mask = (full_sales["product"] == "Chawal") & (full_sales["date"] == MISSING_DAY)
assert mask.sum() == 1, f"no Chawal sale on {MISSING_DAY}; change the day offset"
missing_qty = int(full_sales.loc[mask, "quantity"].sum())
assert missing_qty >= 5, "missing day too small; change the day offset"
sales = full_sales.loc[~mask].reset_index(drop=True)

# ---------- 5. raw sales = recorded sales + planted bad rows ----------
raw = sales[["txn_id", "date", "product", "quantity", "unit_price", "discount_pct"]].copy()
assert len(raw) >= 13, "At least 13 sales rows are required"
sample = raw.sample(n=13, random_state=1).reset_index(drop=True)
next_id = int(raw.txn_id.max()) + 1
duplicates = sample.iloc[0:5].copy()
neg = sample.iloc[5:8].copy();     neg["quantity"] = -2
nodate = sample.iloc[8:11].copy(); nodate["date"] = ""
unk = sample.iloc[11:13].copy();   unk["product"] = "Chawl"
for part in (neg, nodate, unk):
    part["txn_id"] = range(next_id, next_id + len(part))
    next_id += len(part)
raw_bad = pd.concat([raw, duplicates, neg, nodate, unk], ignore_index=True)

# ---------- 6. ground truth + checks (before saving) ----------
sold_rec = sales.groupby("product")["quantity"].sum().reindex(list(PRODUCTS), fill_value=0)
check = inv.copy()
check["expected_stock"] = (check.opening_stock + check["product"].map(bought)
                           - check["product"].map(sold_rec) - check["product"].map(damaged_tot))
check["gap"] = check.counted_stock - check.expected_stock
assert (check.expected_stock >= 0).all(), "expected stock cannot be negative"
gaps = check.set_index("product").gap
assert gaps["Tel"] == -8 and gaps["Doodh"] == -15, "planted gaps missing"
assert gaps["Chawal"] == -missing_qty, "Chawal gap should equal the missing day"
assert (gaps.drop(["Tel", "Doodh", "Chawal"]) == 0).all(), "unexpected extra gaps"

# ---------- 7. save ----------
DATA_DIR.mkdir(parents=True, exist_ok=True)
sales.to_csv(DATA_DIR / "sales.csv", index=False)
raw_bad.to_csv(DATA_DIR / "sales_raw.csv", index=False)
purchases.to_csv(DATA_DIR / "purchases.csv", index=False)
inv[["product", "opening_stock", "counted_stock", "reorder_level"]].to_csv(
    DATA_DIR / "inventory.csv", index=False)

# ---------- 8. summary ----------
print("\n========== VOICOX DATA SUMMARY ==========")
print("Recorded sales rows:", len(sales), "| Raw rows:", len(raw_bad))
print("Purchase rows:", len(purchases), "| Products:", len(inv))
print("\nPlanted data-quality issues in sales_raw.csv:")
print(" duplicates:", len(duplicates), "| negative qty:", len(neg),
      "| missing date:", len(nodate), "| unknown product:", len(unk))
print("\nMissing Chawal sales day:", MISSING_DAY, "| quantity:", missing_qty)
print("\nEXPECTED GAPS (save this):")
print(check.loc[check.gap != 0, ["product", "expected_stock", "counted_stock", "gap"]].to_string(index=False))
print("\nLow-stock products:", inv.loc[inv.counted_stock < inv.reorder_level, "product"].tolist())