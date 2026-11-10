"""Advice questions are refused politely instead of being answered with an unrelated number."""
import pytest
from fastapi.testclient import TestClient

from backend.extractor import extract, is_advice
from backend.main import app

ADVICE = ["How to increase the sales of my shop?", "How can I improve my shop", "Sales badhane ke tarike batao",
          "Dukaan ki bikri kaise badhau", "Give me tips to sell more", "बिक्री बढ़ाने के तरीके बताओ"]
NORMAL = ["Did sales improve this week", "Pichle mahine sabse zyada kya bika", "How much did we sell this week",
          "Is hafte ki bikri pichle hafte se kitni badhi"]


@pytest.mark.parametrize("q", ADVICE)
def test_advice_is_not_answered_with_numbers(q):
    assert extract(q) is None
    assert is_advice(q)


@pytest.mark.parametrize("q", NORMAL)
def test_normal_questions_still_work(q):
    assert extract(q) is not None
    assert not is_advice(q)


@pytest.mark.parametrize("lang", ["hn", "en", "hi"])
def test_the_reply_explains_what_it_can_do(lang):
    with TestClient(app) as c:
        d = c.post("/ask", json={"text": "How to increase the sales of my shop?", "lang": lang}).json()
    assert d["status"] == "reject" and d["result"] is None
    assert ("advice" in d["message"].lower() or "salah" in d["message"].lower() or "सलाह" in d["message"])


OUT_OF_SCOPE = ["Next month kitni bikri hogi", "Predict sales for next week", "Which customer buys the most",
                "Sabse zyada udhar kisne liya", "Kitne employees hain", "Chawal ka bhav kitna hai",
                "What is the price of rice in the market", "Why are my sales low", "Sales kam kyun hai"]
IN_SCOPE = ["Chawal mein gap kyun hai", "Why is rice short", "Tel mein gap kyun hai", "Doodh ki bikri kitni hui",
            "Show me sales", "Kaun sa saman kam bach gaya hai"]


@pytest.mark.parametrize("q", OUT_OF_SCOPE)
def test_questions_the_records_cannot_answer_are_refused(q):
    from backend.extractor import is_out_of_scope
    assert extract(q) is None
    assert is_out_of_scope(q)


@pytest.mark.parametrize("q", IN_SCOPE)
def test_questions_the_records_can_answer_are_not_refused(q):
    from backend.extractor import is_out_of_scope
    assert extract(q) is not None
    assert not is_out_of_scope(q)


def test_the_scope_message_lists_what_it_can_do():
    with TestClient(app) as c:
        d = c.post("/ask", json={"text": "Next month kitni bikri hogi", "lang": "en"}).json()
    assert d["status"] == "reject"
    assert "sales and stock records" in d["message"]


UNKNOWN_PRODUCT = ["Maggi ki bikri kitni hui", "Maggi ka stock kitna hai", "Sales of Maggi last week",
                   "Chocolate kitna bika pichle mahine", "Why is Maggi short"]
BAD_PERIOD = ["Pichle saal ki bikri kitni thi", "Is saal ki bikri", "2025 mein kitna bika", "Show sales for September",
              "Last year sales"]
MISSING_DATA = ["Gst kitna laga", "Rent kitna hai", "Discount kitna diya"]
STILL_FINE = ["Pichle hafte ki bikri", "Is mahine ki bikri", "Kal ki bikri", "Dukaan ki bikri", "Meri bikri kitni hui",
              "Sales of rice last week", "Show me sales", "How much did we sell this week", "Stock of rice",
              "Biscuit kitna bika", "Doodh kitna bika pichle hafte", "Pichle saat din mein kitna bika"]


@pytest.mark.parametrize("q", UNKNOWN_PRODUCT)
def test_a_product_the_shop_does_not_stock_is_named_not_guessed(q):
    assert extract(q) is None
    with TestClient(app) as c:
        d = c.post("/ask", json={"text": q, "lang": "en"}).json()
    assert d["status"] == "reject" and d["result"] is None
    assert "could not find a product" in d["message"] and "Rice" in d["message"]      # lists the real products


@pytest.mark.parametrize("q", BAD_PERIOD)
def test_a_period_outside_the_supported_ones_is_not_answered_with_30_days(q):
    assert extract(q) is None
    with TestClient(app) as c:
        d = c.post("/ask", json={"text": q, "lang": "en"}).json()
    assert d["status"] == "reject" and "3 Aug to 31 Oct 2026" in d["message"]


@pytest.mark.parametrize("q", MISSING_DATA)
def test_data_the_shop_does_not_have_is_refused(q):
    assert extract(q) is None


@pytest.mark.parametrize("q", STILL_FINE)
def test_ordinary_questions_are_not_refused(q):
    assert extract(q) is not None, q


@pytest.mark.parametrize("q,product", [("Mera chawal kahan gaya", "Chawal"), ("Doodh kahan gaya", "Doodh"),
                                       ("Tel kam nikla", "Tel"), ("चावल कहाँ गया", "Chawal")])
def test_where_did_my_stock_go_is_a_why_question(q, product):
    r = extract(q)
    assert r is not None and r.intent == "explain_gap" and r.product == product  