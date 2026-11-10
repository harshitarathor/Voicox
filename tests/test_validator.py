from backend.config import ALIASES, PRODUCTS
from backend.validator import validate

PRODUCT = next(iter(PRODUCTS))
CATEGORY = PRODUCTS[PRODUCT][0]
ALIAS = ALIASES[PRODUCT][0]


def test_valid_query_is_ok():
    v = validate({"intent": "total"})
    assert v.status == "ok"
    assert v.query is not None


def test_unknown_intent_is_rejected():
    v = validate({"intent": "drop_table"})
    assert v.status == "reject"
    assert v.query is None


def test_extra_field_is_rejected():
    v = validate({"intent": "total", "sql": "DROP TABLE sales"})
    assert v.status == "reject"


def test_bad_period_is_rejected():
    assert validate({"intent": "total", "period": "next_year"}).status == "reject"


def test_confidence_out_of_range_is_rejected():
    assert validate({"intent": "total", "confidence": 5}).status == "reject"


def test_alias_becomes_standard_product_name():
    v = validate({"intent": "total", "product": ALIAS})
    assert v.status == "ok"
    assert v.query.product == PRODUCT


def test_unknown_product_asks_to_clarify():
    v = validate({"intent": "total", "product": "Laptop"})
    assert v.status == "clarify"
    assert v.query is None


def test_near_match_asks_to_confirm():
    typo = ALIAS + ALIAS[-1]            # one extra letter at the end
    v = validate({"intent": "total", "product": typo})
    assert v.status == "confirm"
    assert v.query.product == PRODUCT


def test_category_is_normalised():
    v = validate({"intent": "ranked", "group_by": "category",
                  "category": CATEGORY.lower()})
    assert v.status == "ok"
    assert v.query.category == CATEGORY


def test_unknown_category_asks_to_clarify():
    v = validate({"intent": "ranked", "category": "Electronics"})
    assert v.status == "clarify"


def test_compare_without_second_period_asks_to_clarify():
    v = validate({"intent": "compare", "period": "this_week"})
    assert v.status == "clarify"


def test_compare_with_two_periods_is_ok():
    v = validate({"intent": "compare", "period": "this_week",
                  "compare_period": "last_week"})
    assert v.status == "ok"


def test_low_confidence_asks_to_confirm():
    v = validate({"intent": "total", "confidence": 0.3})
    assert v.status == "confirm"
    assert v.query is not None


def test_high_confidence_runs_directly():
    assert validate({"intent": "total", "confidence": 0.95}).status == "ok"