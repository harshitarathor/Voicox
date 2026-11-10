"""Gnani voice layer: Prisma (speech -> text) and Timbre (text -> speech).

Settings come from the smoke test on real audio:
  * Prisma v3.0, language hi-IN + en-IN, format=transliterate -> Roman text with the
    product names spelt right (the other formats mangled "Biscuit").
  * Timbre v3.0, voice Avinash, language hi-en.
Gnani allows one active request per account, so every call waits its turn (_lock).
The API key never leaves this file; errors turn into short messages for the owner.
"""
import logging
import threading
import time
from collections import OrderedDict

import httpx

from backend import config

log = logging.getLogger("voicox.gnani")

STT_URL = "https://api.vachana.ai/stt/v3"
TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"

STT_MODEL = "prisma-v3.0"
STT_LANGUAGES = "hi-IN,en-IN"
STT_FORMAT = "transliterate"
TTS_MODEL = "timbre-v3.0"
TTS_VOICE = "Avinash"
TTS_LANGUAGE = "hi-en"          # Hinglish answers (the default)
TTS_LANGUAGES = {"hn": "hi-en", "en": "en-IN", "hi": "hi-IN"}   # by the answer's language
TTS_SAMPLE_RATE = 24000

TIMEOUT = 30                    # seconds per attempt
RETRIES = 2                     # extra attempts for busy / temporary failures
MAX_SPEAK_CHARS = 600           # the Timbre playground allows 800 per request
CACHE_SIZE = 64                 # same answer spoken twice costs credits only once

_lock = threading.Lock()        # one Gnani request at a time
_cache_lock = threading.Lock()  # cache check + paid call + store happen as one step
_cache: "OrderedDict[str, bytes]" = OrderedDict()
_sleep = time.sleep             # tests replace this


class GnaniError(Exception):
    """Something the voice service did or did not do. `message` is safe to show."""

    def __init__(self, code: str, message: str, http: int = 503):
        super().__init__(code)
        self.code, self.message, self.http = code, message, http


_MESSAGES = {
    "not_configured": ("Awaaz wali service set nahi hai. Likhkar poochhiye.", 503),
    "auth": ("Awaaz wali service ki key sahi nahi hai. Likhkar poochhiye.", 503),
    "credit": ("Awaaz wali service ka credit khatam ho gaya. Likhkar poochhiye.", 503),
    "busy": ("Awaaz wali service abhi vyast hai. Thodi der baad koshish kijiye.", 503),
    "bad_audio": ("Awaaz record theek se nahi hui. Dobara bolkar dekhiye.", 400),
    "unavailable": ("Awaaz wali service abhi nahi mil rahi. Likhkar poochhiye.", 503),
}


def _error(code: str) -> GnaniError:
    message, http = _MESSAGES[code]
    return GnaniError(code, message, http)


def configured() -> bool:
    return bool(config.GNANI_API_KEY)


def _post(url: str, key: str, **kw) -> httpx.Response:
    return httpx.post(url, headers={"X-API-Key-ID": key}, timeout=TIMEOUT, **kw)


def _request(url: str, **kw) -> httpx.Response:
    """One call at a time, with a short retry when Gnani is busy or briefly down."""
    key = config.GNANI_API_KEY
    if not key:
        raise _error("not_configured")
    with _lock:
        last = "unavailable"
        for attempt in range(RETRIES + 1):
            try:
                r = _post(url, key, **kw)
            except httpx.HTTPError:
                log.warning("gnani network error (attempt %d)", attempt + 1)
                last = "unavailable"
            else:
                if r.status_code == 200:
                    return r
                log.warning("gnani %s -> %s %s", url.rsplit("/", 1)[-1], r.status_code, r.text[:200])
                if r.status_code in (401, 403):
                    raise _error("auth")
                if r.status_code == 402:
                    raise _error("credit")
                if r.status_code == 400:
                    raise _error("bad_audio")
                last = "busy" if r.status_code == 429 else "unavailable"
                if r.status_code not in (429, 502, 503, 504):
                    break               # a real failure: retrying will not help
            if attempt < RETRIES:
                _sleep(1.5 * (attempt + 1))
        raise _error(last)


_FILENAMES = {"audio/wav": "audio.wav", "audio/x-wav": "audio.wav", "audio/wave": "audio.wav",
              "audio/mpeg": "audio.mp3", "audio/mp3": "audio.mp3", "audio/ogg": "audio.ogg",
              "audio/flac": "audio.flac", "audio/aac": "audio.aac", "audio/mp4": "audio.m4a",
              "audio/x-m4a": "audio.m4a"}


def transcribe(audio: bytes, content_type: str = "audio/wav") -> str:
    """Speech -> Roman text. Returns "" when nothing was heard."""
    # browsers send things like "audio/wav; charset=..." : keep only the type
    content_type = (content_type or "audio/wav").split(";")[0].strip().lower()
    name = _FILENAMES.get(content_type, "audio.wav")
    r = _request(STT_URL,
                 files={"audio_file": (name, audio, content_type)},
                 data={"model": STT_MODEL, "language_code": STT_LANGUAGES, "format": STT_FORMAT})
    try:
        return (r.json().get("transcript") or "").strip()
    except ValueError:
        raise _error("unavailable")


def _clip(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= MAX_SPEAK_CHARS:
        return text
    cut = text[:MAX_SPEAK_CHARS]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[:end + 1] if end > 100 else cut


def synthesize(text: str, lang: str = "hn") -> bytes:
    """Text -> WAV bytes. The same text is served from memory the second time."""
    text = _clip(text or "")
    if not text:
        raise _error("unavailable")
    language = TTS_LANGUAGES.get(lang, TTS_LANGUAGE) if lang != "hn" else TTS_LANGUAGE
    key = (language, text)
    # One lock around check + call + store: two requests for the same new answer
    # make one paid call, and nothing is evicted while another thread reads it.
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
        try:
            r = _request(TTS_URL, json={
                "text": text, "voice": TTS_VOICE, "model": TTS_MODEL, "language": language,
                "speed": 1.0,
                "audio_config": {"sample_rate": TTS_SAMPLE_RATE, "num_channels": 1,
                                 "sample_width": 2, "encoding": "linear_pcm",
                                 "container": "wav"}})
        except GnaniError as e:
            if e.code == "bad_audio":       # a 400 here is our request, not the owner's recording
                raise _error("unavailable")
            raise
        if not r.content:
            raise _error("unavailable")
        _cache[key] = r.content
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
        return r.content
