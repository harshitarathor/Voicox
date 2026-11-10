"""Gnani voice smoke test (v2). Run from the Voicox folder, with the venv active:

    python smoke_test_gnani.py                 # Timbre speaks 3 samples, Prisma reads each back 3 ways
    python smoke_test_gnani.py my_voice.wav    # Prisma reads YOUR recording 3 ways (3 calls per file)

Needs GNANI_API_KEY in the .env file. Calls run one after another (Gnani allows
one active request at a time). Fields come from docs.gnani.ai (STT REST, Prisma v3.0, TTS REST).

Cost: default run = 3 Timbre + 9 Prisma calls (about 12). Own recording = 3 calls per file.
"""
import sys
import time
import wave
from pathlib import Path

import httpx

from backend.config import ALIASES, GNANI_API_KEY, PROJECT_ROOT

STT_URL = "https://api.vachana.ai/stt/v3"
TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"
OUT = PROJECT_ROOT / "smoke_test_output"

ROMAN = "Pichle mahine sabse zyada Biscuit bika, 434 unit."
DEVANAGARI = "पिछले महीने सबसे ज्यादा बिस्कुट बिका, चार सौ चौंतीस यूनिट।"

# (file label, text, model, voice, language). Sample rate 24 kHz: Prisma accepts 8-44.1 kHz only.
TTS_SAMPLES = [
    ("v25_poorvi_roman", ROMAN, "timbre-v2.5", "Poorvi", "hi-en"),
    ("v30_shivani_roman", ROMAN, "timbre-v3.0", "Shivani", "hi-en"),
    ("v30_shivani_devanagari", DEVANAGARI, "timbre-v3.0", "Shivani", "hi-IN"),
]

# Product words to favour (Roman + Devanagari aliases), well under the 200-item limit.
KEYTERMS = sorted({a for names in ALIASES.values() for a in names})

# (label, extra form fields). All use model=prisma-v3.0 and two likely languages.
STT_VARIANTS = [
    ("transcribe", {"format": "transcribe"}),
    ("transliterate", {"format": "transliterate"}),
    ("transcribe+keyterms", {"format": "transcribe", "keyterms": ",".join(KEYTERMS),
                             "topic": "kirana shop owner asking about sales, stock and wastage"}),
]


def looks_right(text):
    """Rough check on the planted sentence: product word + the number 434."""
    t = (text or "").casefold()
    product = any(a.casefold() in t for a in ALIASES["Biscuit"])
    number = "434" in t or "चौंतीस" in t or "chautis" in t or "chaunteesh" in t
    return product, number


def post(client, url, **kw):
    """One request; waits and retries once if Gnani says another request is still active (429)."""
    r = client.post(url, **kw)
    if r.status_code == 429:
        time.sleep(2)
        r = client.post(url, **kw)
    return r


def explain(r):
    hint = {401: "key missing/invalid", 402: "out of credit", 403: "key lacks this service",
            429: "rate limited"}.get(r.status_code, "")
    return f"status={r.status_code} {hint}  {r.text[:300]}"


def speak(client, label, text, model, voice, language):
    body = {"text": text, "voice": voice, "model": model, "language": language, "speed": 1.0,
            "audio_config": {"sample_rate": 24000, "num_channels": 1, "sample_width": 2,
                             "encoding": "linear_pcm", "container": "wav"}}
    t0 = time.time()
    r = post(client, TTS_URL, json=body)
    took = time.time() - t0
    if r.status_code != 200:
        print(f"   {label}: TIMBRE FAILED  {explain(r)}")
        return None
    path = OUT / f"timbre_{label}.wav"
    path.write_bytes(r.content)
    print(f"   {label}: {model} {voice} {language}  {len(r.content) / 1024:.0f} KB  {took:.1f}s -> {path.name}")
    return path


def transcribe(client, path, label, extra):
    data = {"model": "prisma-v3.0", "language_code": "hi-IN,en-IN", **extra}
    t0 = time.time()
    with open(path, "rb") as f:
        r = post(client, STT_URL, files={"audio_file": (path.name, f)}, data=data)
    took = time.time() - t0
    if r.status_code != 200:
        print(f"   {label:<20} FAILED  {explain(r)}")
        return
    j = r.json()
    text = j.get("transcript")
    product, number = looks_right(text)
    print(f"   {label:<20} {took:.1f}s  lang={j.get('detected_language_code', '-')}  "
          f"product={'yes' if product else 'NO'} number={'yes' if number else 'NO'}\n"
          f"      -> {text!r}")


def wav_seconds(path):
    try:
        with wave.open(str(path)) as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return None            # not a plain WAV: skip the length check


def run(client, recordings):
    OUT.mkdir(exist_ok=True)
    files = []
    for p in map(Path, recordings):
        secs = wav_seconds(p)
        if secs and secs > 30:
            print(f"! {p.name} is {secs:.0f}s; Prisma REST accepts 30s at most. Trim it.")
        files.append(p)

    if not files:
        print("\n1) Timbre: text -> speech (3 samples)")
        for label, text, model, voice, lang in TTS_SAMPLES:
            path = speak(client, label, text, model, voice, lang)
            if path:
                files.append(path)
        print("\nListen to the .wav files in smoke_test_output/ and tell me which sounds best.")

    print("\n2) Prisma v3.0: speech -> text (language hi-IN,en-IN; three settings)")
    for path in files:
        print(f" file: {path.name}")
        for label, extra in STT_VARIANTS:
            transcribe(client, path, label, extra)
    print("\nDone. Paste this whole output back, plus your credit balance before and after.")


def main():
    if not GNANI_API_KEY:
        sys.exit("GNANI_API_KEY is empty. Put it in the .env file in the Voicox folder:\n"
                 "GNANI_API_KEY=your_key_here")
    for p in sys.argv[1:]:
        if not Path(p).exists():
            sys.exit(f"File not found: {p}")
    with httpx.Client(headers={"X-API-Key-ID": GNANI_API_KEY}, timeout=60) as client:
        run(client, sys.argv[1:])


if __name__ == "__main__":
    main()