"""Voice layer tests. Gnani is replaced by a fake: no network, no credits."""
import threading

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import gnani, main

KEY = "test-key-123"
WAV = b"RIFF....WAVEfmt fake audio"


def reply(status, **kw):
    return httpx.Response(status, request=httpx.Request("POST", "https://x"), **kw)


@pytest.fixture(autouse=True)
def fake_gnani(monkeypatch):
    monkeypatch.setattr(gnani.config, "GNANI_API_KEY", KEY)
    monkeypatch.setattr(gnani, "_sleep", lambda s: None)
    gnani._cache.clear()
    calls = []
    script = {"responses": [reply(200, json={"transcript": "pichle mahine sabse zyada kya bika"})]}

    def fake_post(url, key, **kw):
        calls.append({"url": url, "key": key, **kw})
        item = script["responses"][min(len(calls), len(script["responses"])) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(gnani, "_post", fake_post)
    return type("Fake", (), {"calls": calls, "script": script})


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


# ---------- Prisma ----------
def test_transcribe_sends_the_settings_we_measured(fake_gnani):
    assert gnani.transcribe(WAV, "audio/wav") == "pichle mahine sabse zyada kya bika"
    call = fake_gnani.calls[0]
    assert call["key"] == KEY
    assert call["data"] == {"model": "prisma-v3.0", "language_code": "hi-IN,en-IN",
                            "format": "transliterate"}
    assert call["files"]["audio_file"][0] == "audio.wav"


def test_busy_then_ok_is_retried(fake_gnani):
    fake_gnani.script["responses"] = [reply(429, text="busy"),
                                      reply(200, json={"transcript": "aaj kitni bikri hui"})]
    assert gnani.transcribe(WAV) == "aaj kitni bikri hui"
    assert len(fake_gnani.calls) == 2


def test_always_busy_gives_up_with_a_clear_message(fake_gnani):
    fake_gnani.script["responses"] = [reply(429, text="busy")]
    with pytest.raises(gnani.GnaniError) as e:
        gnani.transcribe(WAV)
    assert e.value.code == "busy" and len(fake_gnani.calls) == 3


@pytest.mark.parametrize("status, code", [(401, "auth"), (403, "auth"), (402, "credit"),
                                          (400, "bad_audio")])
def test_errors_are_not_retried(fake_gnani, status, code):
    fake_gnani.script["responses"] = [reply(status, text="nope")]
    with pytest.raises(gnani.GnaniError) as e:
        gnani.transcribe(WAV)
    assert e.value.code == code and len(fake_gnani.calls) == 1


def test_server_error_is_not_retried(fake_gnani):
    fake_gnani.script["responses"] = [reply(500, text="boom")]
    with pytest.raises(gnani.GnaniError) as e:
        gnani.transcribe(WAV)
    assert e.value.code == "unavailable" and len(fake_gnani.calls) == 1


def test_network_failure_is_retried_then_reported(fake_gnani):
    fake_gnani.script["responses"] = [httpx.ConnectError("down")]
    with pytest.raises(gnani.GnaniError) as e:
        gnani.transcribe(WAV)
    assert e.value.code == "unavailable" and len(fake_gnani.calls) == 3


def test_no_key_means_no_call(fake_gnani, monkeypatch):
    monkeypatch.setattr(gnani.config, "GNANI_API_KEY", "")
    with pytest.raises(gnani.GnaniError) as e:
        gnani.transcribe(WAV)
    assert e.value.code == "not_configured" and fake_gnani.calls == []


# ---------- Timbre ----------
def test_synthesize_uses_avinash_and_remembers_the_answer(fake_gnani):
    fake_gnani.script["responses"] = [reply(200, content=WAV)]
    assert gnani.synthesize("Chawal ka gap satrah kilo hai.") == WAV
    assert gnani.synthesize("Chawal ka gap satrah kilo hai.") == WAV
    assert len(fake_gnani.calls) == 1                         # second one came from memory
    body = fake_gnani.calls[0]["json"]
    assert (body["voice"], body["model"], body["language"]) == ("Avinash", "timbre-v3.0", "hi-en")


def test_long_text_is_cut_at_a_sentence(fake_gnani):
    fake_gnani.script["responses"] = [reply(200, content=WAV)]
    gnani.synthesize("Yeh ek line hai. " * 80)
    sent = fake_gnani.calls[0]["json"]["text"]
    assert len(sent) <= gnani.MAX_SPEAK_CHARS and sent.endswith(".")


# ---------- routes ----------
def test_voice_status(client):
    assert client.get("/voice-status").json() == {"configured": True}


def test_ask_audio_runs_the_same_pipeline_as_typing(client, fake_gnani):
    r = client.post("/ask-audio", content=WAV, headers={"content-type": "audio/wav"})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ok"
    assert body["transcript"] == "pichle mahine sabse zyada kya bika"
    assert body["query"]["intent"] == "ranked" and body["query"]["period"] == "last_month"
    assert body["result"]["spoken"]


def test_ask_audio_survives_the_misheard_period(client, fake_gnani):
    fake_gnani.script["responses"] = [reply(200, json={"transcript": "pikal mahine sabse zyada kya bika"})]
    body = client.post("/ask-audio", content=WAV, headers={"content-type": "audio/wav"}).json()
    assert body["query"]["period"] == "last_month"


def test_ask_audio_empty_recording(client, fake_gnani):
    r = client.post("/ask-audio", content=b"", headers={"content-type": "audio/wav"})
    assert r.json()["status"] == "reject" and fake_gnani.calls == []


def test_ask_audio_nothing_heard(client, fake_gnani):
    fake_gnani.script["responses"] = [reply(200, json={"transcript": ""})]
    r = client.post("/ask-audio", content=WAV, headers={"content-type": "audio/wav"})
    assert r.json()["status"] == "reject"


def test_ask_audio_too_big(client, fake_gnani):
    r = client.post("/ask-audio", content=b"x" * (main.MAX_AUDIO_BYTES + 1),
                    headers={"content-type": "audio/wav"})
    assert r.status_code == 413 and fake_gnani.calls == []


def test_ask_audio_gnani_down_says_so_without_leaking_the_key(client, fake_gnani):
    fake_gnani.script["responses"] = [reply(402, text=f"no credit for {KEY}")]
    r = client.post("/ask-audio", content=WAV, headers={"content-type": "audio/wav"})
    assert r.status_code == 503 and r.json()["status"] == "error"
    assert "credit" in r.json()["message"] and KEY not in r.text


def test_speak_returns_wav(client, fake_gnani):
    fake_gnani.script["responses"] = [reply(200, content=WAV)]
    r = client.post("/speak", json={"text": "Namaste"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content == WAV


def test_speak_failure_and_bad_input(client, fake_gnani):
    fake_gnani.script["responses"] = [reply(429, text="busy")]
    r = client.post("/speak", json={"text": "Namaste"})
    assert r.status_code == 503 and r.json()["status"] == "error"
    assert client.post("/speak", json={"text": ""}).status_code == 422
    assert client.post("/speak", json={"text": "x" * 601}).status_code == 422


# ---------- review fixes ----------
def test_browser_content_type_suffix_is_cleaned(fake_gnani):
    gnani.transcribe(WAV, "Audio/WAV; charset=binary")
    name, _, ctype = fake_gnani.calls[0]["files"]["audio_file"]
    assert (name, ctype) == ("audio.wav", "audio/wav")


def test_timbre_400_is_not_blamed_on_the_recording(fake_gnani):
    fake_gnani.script["responses"] = [reply(400, text="bad voice")]
    with pytest.raises(gnani.GnaniError) as e:
        gnani.synthesize("Namaste")
    assert e.value.code == "unavailable"
    assert "record" not in e.value.message


def test_same_new_answer_from_many_threads_is_paid_once(fake_gnani):
    fake_gnani.script["responses"] = [reply(200, content=WAV)]
    out = []
    threads = [threading.Thread(target=lambda: out.append(gnani.synthesize("Ek hi jawab hai.")))
               for _ in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert out == [WAV] * 8 and len(fake_gnani.calls) == 1