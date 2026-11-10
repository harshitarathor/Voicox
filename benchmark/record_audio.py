"""Record the benchmark audio files with your microphone (no Gnani credits are used here).

One-time install:   pip install sounddevice
Run from the project folder:
    python benchmark/record_audio.py              # asks you to say each marked question, one by one
    python benchmark/record_audio.py --group noisy  # only one group (hinglish, hindi, english, noisy)
    python benchmark/record_audio.py --redo       # record again even if a file already exists

Each recording is 6 seconds, saved as benchmark/audio/<group>/<id>.wav (16 kHz, mono).
Say the sentence shown on screen in your own natural way. For the 'noisy' group, record with a fan, a TV or
street noise in the background, because that is how a real shop sounds.
"""
import argparse
import csv
import sys
import wave
from pathlib import Path

BENCH = Path(__file__).resolve().parent
RATE = 16000
SECONDS = 6
NOISE_HINT = "NOISY take: switch on a fan or TV, or record near a road, then speak normally."


def load():
    with open(BENCH / "questions.csv", encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if r["record"].strip().lower() == "yes"]


def save_wav(path, samples):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(samples.tobytes())


def main():
    ap = argparse.ArgumentParser(description="Record the Voicox benchmark audio")
    ap.add_argument("--group", choices=["hinglish", "hindi", "english", "noisy"])
    ap.add_argument("--redo", action="store_true")
    a = ap.parse_args()
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError:
        sys.exit("Install the recorder first:  pip install sounddevice")

    todo = [q for q in load() if (not a.group or q["group"] == a.group)
            and (a.redo or not (BENCH / "audio" / q["group"] / f"{q['id']}.wav").exists())]
    if not todo:
        print("Nothing to record: every file already exists (use --redo to record again).")
        return
    print(f"{len(todo)} questions to record. Press Enter to start each one, or type q then Enter to stop.\n")
    for i, q in enumerate(todo, 1):
        path = BENCH / "audio" / q["group"] / f"{q['id']}.wav"
        while True:
            print(f"[{i}/{len(todo)}] {q['id']} ({q['group']})")
            if q["group"] == "noisy":
                print("   " + NOISE_HINT)
            print(f"   SAY:  {q['question']}")
            if q["roman"]:
                print(f"   (in letters: {q['roman']})")
            if input("   Press Enter, then speak (q = stop): ").strip().lower() == "q":
                print("Stopped. Run the script again later to continue.")
                return
            print(f"   Recording {SECONDS} seconds ...")
            samples = sd.rec(int(SECONDS * RATE), samplerate=RATE, channels=1, dtype="int16")
            sd.wait()
            peak = int(np.abs(samples).max())
            if peak < 800:
                print("   Too quiet: nothing was heard. Check the microphone and try again.\n")
                continue
            save_wav(path, samples)
            print(f"   Saved {path.relative_to(BENCH.parent)}\n")
            if input("   Keep it? Enter = yes, r = record again: ").strip().lower() != "r":
                break
            print()
    print("All done. Now run:  python benchmark/run_benchmark.py")


if __name__ == "__main__":
    main()
