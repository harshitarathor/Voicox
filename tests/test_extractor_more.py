"""Questions found while trying the app by hand: they used to give a wrong or surprising answer."""
import pytest

from backend.extractor import extract


@pytest.mark.parametrize("text", [
    "Pichle mahine ka profit kitna hua",
    "Chawal ka munafa kitna hai",
    "पिछले महीने का मुनाफा कितना हुआ",
    "What is my profit margin",
])
def test_profit_questions_are_refused_not_answered_with_sales(text):
    assert extract(text) is None


@pytest.mark.parametrize("text", [
    "Chawal ka stock records se match karta hai kya",
    "Kya Doodh ka stock match kar raha hai",
])
def test_does_the_stock_match_is_a_gap_question_not_a_low_stock_question(text):
    assert extract(text).intent == "stock_gap"


def test_devanagari_most_sold_means_one_product():
    q = extract("पिछले महीने सबसे ज्यादा क्या बिका")
    assert q.intent == "ranked" and q.limit == 1


def test_english_sell_is_understood():
    q = extract("How much rice did we sell last week")
    assert q.intent == "total" and q.product == "Chawal" and q.period == "last_week"
    assert q.metric == "quantity"
