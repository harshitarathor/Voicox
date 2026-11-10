"""Answers come back in the language chosen on the page: Hinglish (hn, the default), English (en), Hindi (hi).

Only the words change. The numbers must be the same in all three, because they come from engine.py.
"""
import re

import pytest
from fastapi.testclient import TestClient

from backend import gnani, main, phrases

QUESTIONS = [
    "Aaj ki total bikri kitni hui",
    "Pichle mahine sabse zyada kya bika",
    "Pichle mahine top 3 products batao",
    "Is hafte ki bikri pichle hafte se kaisi rahi",
    "Pichle 30 din ka sales trend dikhao",
    "Kaunsa stock kam hai",
    "Chawal ka stock kitna hai",
    "Kahan stock mismatch hai",
    "Chawal mein gap kyun hai",
    "Doodh ka stock kam kyun hai",
    "Kitna maal kharab hua pichle mahine",
    "Cheeni ka gap kyun hai",
]
HINGLISH_WORDS = re.compile(r"\b(bika|bikri|hazaar|rupaye|raha|rahi|mahine|hafte|mein|ka|ki|hai|nahi|kam|zyada)\b")


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app) as c:
        yield c


def ask(client, text, lang=None):
    body = {"text": text} if lang is None else {"text": text, "lang": lang}
    return client.post("/ask", json=body).json()


def every_text(d):
    """All the wording in one reply: the answer, alerts and causes."""
    r = d["result"]
    parts = [r["spoken"], r["disclaimer"] or ""] + [a["message"] for a in r["alerts"]]
    for c in r["causes"]:
        parts += [c["headline"], c["detail"], c["check_next"]]
    return " ".join(parts)


@pytest.mark.parametrize("text", QUESTIONS)
def test_the_numbers_are_the_same_in_every_language(client, text):
    def digits(lang):
        d = ask(client, text, lang)
        assert d["status"] == "ok"
        return sorted(re.findall(r"\d+", every_text(d)))
    assert digits("hn") == digits("en") == digits("hi")


@pytest.mark.parametrize("text", QUESTIONS)
def test_english_has_no_hinglish_in_it(client, text):
    d = ask(client, text, "en")
    assert not HINGLISH_WORDS.search(every_text(d).lower()), every_text(d)


@pytest.mark.parametrize("text", QUESTIONS)
def test_hindi_is_all_devanagari_apart_from_digits(client, text):
    d = ask(client, text, "hi")
    assert not re.search(r"[A-Za-z]", every_text(d)), every_text(d)


def test_no_language_given_means_hinglish_as_before(client):
    for lang in (None, "xx", "", "EN"):
        assert ask(client, "Aaj ki total bikri kitni hui", lang)["result"]["spoken"] == \
            "Aaj ki total bikri 4 hazaar 600 rupaye rahi."


def test_the_three_wordings_of_one_answer(client):
    q = "Pichle mahine sabse zyada kya bika"
    assert ask(client, q, "hn")["result"]["spoken"] == "Pichle mahine sabse zyada Biscuit bika, 434 unit."
    assert ask(client, q, "en")["result"]["spoken"] == "Last month, Biscuits sold the most: 434 units."
    assert "बिस्कुट" in ask(client, q, "hi")["result"]["spoken"]


def test_hinglish_voice_names_products_in_devanagari_but_the_screen_does_not(client):
    d = ask(client, "Chawal ki bikri pichle mahine kitni thi", "hn")
    assert "Chawal" in d["result"]["spoken"] and "चावल" not in d["result"]["spoken"]
    assert "चावल" in d["voice"] and "Chawal" not in d["voice"]


def test_hindi_voice_has_numbers_as_words(client):
    d = ask(client, "Aaj ki total bikri kitni hui", "hi")
    assert re.search(r"\d", d["result"]["spoken"])               # digits on screen
    assert not re.search(r"\d", d["voice"])                      # words for the speaker
    assert "चार हज़ार छह सौ" in d["voice"]


def test_english_voice_is_the_screen_text(client):
    d = ask(client, "Aaj ki total bikri kitni hui", "en")
    assert d["voice"] == d["result"]["spoken"]


def test_questions_in_every_language_get_answered_in_the_chosen_one(client):
    d = ask(client, "पिछले महीने सबसे ज्यादा क्या बिका", "en")
    assert d["result"]["spoken"].startswith("Last month")


def test_messages_are_translated_too(client):
    assert "did not understand" in ask(client, "Kal mausam kaisa hoga", "en")["message"]
    assert "समझ नहीं आया" in ask(client, "Kal mausam kaisa hoga", "hi")["message"]
    assert "samajh nahi aaya" in ask(client, "Kal mausam kaisa hoga", "hn")["message"]
    assert ask(client, "Chaval mein gap kyun hai", "en")["message"] == "Do you mean Rice?"
    assert ask(client, "Chaval mein gap kyun hai", "hi")["message"] == "क्या आप चावल कह रहे हैं?"


def test_the_ready_made_lists_follow_the_language(client):
    en = client.get("/stock-gaps?lang=en").json()["result"]["alerts"][0]["message"]
    hi = client.get("/low-stock?lang=hi").json()["result"]["alerts"][0]["message"]
    assert en.startswith("Rice may be short") and "स्टॉक कम है" in hi
    assert client.get("/stock-gaps").json()["result"]["alerts"][0]["message"].startswith("Chawal mein")


def test_audio_replies_use_the_chosen_language(client, monkeypatch):
    monkeypatch.setattr(main.gnani, "transcribe", lambda audio, content_type: "")
    en = client.post("/ask-audio?lang=en", content=b"x", headers={"content-type": "audio/wav"}).json()
    hi = client.post("/ask-audio?lang=hi", content=b"x", headers={"content-type": "audio/wav"}).json()
    assert "could not hear" in en["message"] and "साफ़ नहीं आई" in hi["message"]


def test_the_speaker_gets_the_right_language(monkeypatch):
    seen = []

    class Reply:
        content = b"RIFFwav"

    def fake_request(url, **kw):
        seen.append(kw["json"]["language"])
        return Reply()

    monkeypatch.setattr(gnani, "_request", fake_request)
    gnani._cache.clear()
    for lang in ("hn", "en", "hi"):
        gnani.synthesize("namaste", lang)
    gnani.synthesize("namaste", "en")                           # same text, same language: from memory
    assert seen == ["hi-en", "en-IN", "hi-IN"]
    gnani._cache.clear()


def test_every_sentence_exists_in_all_three_languages():
    for key, by_lang in phrases.S.items():
        assert set(by_lang) == set(phrases.LANGS), key