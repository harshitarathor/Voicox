import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# ---------- paths ----------
BASE_DIR = Path(__file__).resolve().parent          # .../backend
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"

# read keys from the .env file in the project root (file may be missing; that's fine)
load_dotenv(PROJECT_ROOT / ".env")

# ---------- API keys (set these in .env, never in code) ----------
# Empty here on purpose: the app and text-path tests run without keys.
# gnani.py raises a clear error only when a voice call is actually made.
GNANI_API_KEY = os.getenv("GNANI_API_KEY", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# ---------- fixed "today" so the generator, engine and tests all agree ----------
TODAY = date(2026, 10, 31)

# ---------- products: name -> (category, unit_price, average daily demand) ----------
PRODUCTS = {
    "Chawal":  ("Grocery", 60, 12),
    "Atta":    ("Grocery", 45, 10),
    "Tel":     ("Grocery", 140, 4),
    "Cheeni":  ("Grocery", 42, 8),
    "Daal":    ("Grocery", 110, 5),
    "Doodh":   ("Dairy", 30, 15),
    "Dahi":    ("Dairy", 25, 9),
    "Biscuit": ("Snacks", 20, 14),
    "Namkeen": ("Snacks", 35, 7),
    "Sabun":   ("Home", 40, 6),
}

# ---------- every way a user might say or write each product -> standard name ----------
ALIASES = {
    "Chawal":  ["chawal", "chaawal", "rice", "चावल"],
    "Atta":    ["atta", "aata", "flour", "wheat flour", "आटा"],
    "Tel":     ["tel", "oil", "cooking oil", "तेल"],
    "Cheeni":  ["cheeni", "chini", "sugar", "चीनी"],
    "Daal":    ["daal", "dal", "lentils", "दाल"],
    "Doodh":   ["doodh", "dudh", "milk", "दूध"],
    "Dahi":    ["dahi", "curd", "yogurt", "yoghurt", "दही"],
    "Biscuit": ["biscuit", "biscuits", "biskut", "बिस्कुट"],
    "Namkeen": ["namkeen", "namkin", "savoury snacks", "नमकीन"],
    "Sabun":   ["sabun", "soap", "साबुन"],
}

# shown on screen next to the standard name, e.g. "Chawal (Rice)"
ENGLISH_NAMES = {
    "Chawal": "Rice", "Atta": "Flour", "Tel": "Oil", "Cheeni": "Sugar",
    "Daal": "Lentils", "Doodh": "Milk", "Dahi": "Curd", "Biscuit": "Biscuits",
    "Namkeen": "Savoury snacks", "Sabun": "Soap",
}

# ---------- check the config at import time ----------
assert PRODUCTS, "PRODUCTS cannot be empty"
assert set(ALIASES) == set(PRODUCTS), "ALIASES and PRODUCTS must list the same products"
assert set(ENGLISH_NAMES) == set(PRODUCTS), "ENGLISH_NAMES and PRODUCTS must list the same products"

for _product in PRODUCTS:
    assert ALIASES[_product], f"No aliases defined for {_product}"
    assert ENGLISH_NAMES[_product].strip(), f"Missing English name for {_product}"
    assert _product.lower() in [a.lower() for a in ALIASES[_product]], \
        f"{_product}: its own name should be in its alias list"
    