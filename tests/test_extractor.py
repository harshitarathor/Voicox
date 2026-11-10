import pytest

from backend.extractor import extract, keyword_extract
from backend.validator import validate

CASES = [
    ("Pichle mahine sabse zyada kya bika?",
     dict(intent="ranked", order="desc", period="last_month", metric="quantity",
          group_by="product")),
    ("Kahan stock mismatch hai?", dict(intent="stock_gap")),
    ("Chawal mein gap kyun hai?", dict(intent="explain_gap", product="Chawal")),
    ("Doodh mein gap kyu hai", dict(intent="explain_gap", product="Doodh")),
    ("Kaunsa stock kam hai?", dict(intent="low_stock")),
    ("Aaj kitni bikri hui?", dict(intent="total", metric="revenue", period="today")),
    ("Chawal kitna bika aaj", dict(intent="total", metric="quantity", period="today",
                                   product="Chawal")),
    ("Is hafte ki bikri pichle hafte se kaisi rahi?",
     dict(intent="compare", period="this_week", compare_period="last_week",
          metric="revenue")),
    ("Sabse kam bikne wale products kaun se hain?", dict(intent="ranked", order="asc")),
    ("Kharab maal kitna hai", dict(intent="wastage")),
    ("Tel ka stock mismatch", dict(intent="stock_gap", product="Tel")),
    ("Last month top 3 products by revenue",
     dict(intent="ranked", period="last_month", limit=3, metric="revenue")),
    ("Which category sold the most", dict(intent="ranked", group_by="category")),
    ("Dahi ka trend dikhao", dict(intent="trend", product="Dahi")),
    ("चावल में गैप क्यों है", dict(intent="explain_gap", product="Chawal")),
]


@pytest.mark.parametrize("text, expected", CASES)
def test_keyword_extraction(text, expected):
    q = keyword_extract(text)
    assert q is not None, text
    for field, value in expected.items():
        assert getattr(q, field) == value, f"{text!r}: {field}"


def test_unrelated_text_returns_none():
    assert keyword_extract("hello") is None
    assert keyword_extract("") is None


def test_extract_wrapper_matches_keyword_layer():
    assert extract("Kahan stock mismatch hai?") == keyword_extract("Kahan stock mismatch hai?")


def test_misspelt_product_is_sent_to_confirmation():
    v = validate(keyword_extract("Chaval mein gap kyun hai"))
    assert v.status == "confirm"
    assert v.query.product == "Chawal"


def test_compare_with_one_period_asks_for_the_other():
    v = validate(keyword_extract("Pichle hafte se compare karo"))
    assert v.status == "clarify"


def test_explain_without_product_is_not_run_blindly():
    v = validate(keyword_extract("Gap kyun hai"))
    assert v.status == "confirm"


@pytest.mark.parametrize("text", [c[0] for c in CASES])
def test_every_extraction_passes_the_validator(text):
    v = validate(keyword_extract(text))
    assert v.status in ("ok", "confirm")