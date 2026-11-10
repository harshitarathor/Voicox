"""Questions as Gnani Prisma writes them (format=transliterate): Roman text, numbers as words."""
import pytest

from backend.extractor import extract


@pytest.mark.parametrize("text, period", [
    ("pichle mahine sabse zyada kya bika", "last_month"),
    ("pikal mahine sabse zyada biscuit bikay four hundred thirty four unit.", "last_month"),
    ("pikal mahine sabse zyada kya bika", "last_month"),
    ("is mahine kitna bika", "this_month"),
])
def test_misheard_pichle_still_gives_last_month(text, period):
    assert extract(text).period == period


@pytest.mark.parametrize("text, limit", [
    ("top three products this month", 3),
    ("top teen products pichle hafte", 3),
    ("top 4 products", 4),
    ("sabse zyada kya bika", 1),
])
def test_spoken_numbers_in_the_limit(text, limit):
    assert extract(text).limit == limit


def test_unsupported_day_span_asks_first():
    assert extract("pichle saat din mein kitna bika").confidence < 0.6
    assert extract("pichle 7 din ka total").confidence < 0.6


def test_thirty_days_runs_without_asking():
    assert extract("pichle 30 din ka total").confidence >= 0.6


def test_unrelated_word_before_mahine_is_not_changed():
    assert extract("kitne mahine ka sales").period == "last_30_days"