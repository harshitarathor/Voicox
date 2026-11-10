"""The benchmark set and its scoring code (no Gnani calls, no credits)."""
import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("run_benchmark", ROOT / "benchmark" / "run_benchmark.py")
rb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb)


def rows():
    with open(ROOT / "benchmark" / "questions.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_thirty_questions_in_four_groups():
    r = rows()
    assert len(r) == 30
    assert len({x["id"] for x in r}) == 30
    groups = {x["group"] for x in r}
    assert groups == {"hinglish", "hindi", "english", "noisy"}
    assert sum(x["record"] == "yes" for x in r) == 20
    assert sum("why:" in x["check"] for x in r) >= 3          # the "kyun?" questions


def test_every_check_is_understood():
    for x in rows():
        assert rb.expected_query(x["check"])["intent"]


def test_hindi_questions_carry_a_roman_version():
    for x in rows():
        if x["group"] == "hindi":
            assert x["roman"]


def test_typed_run_is_fully_correct_and_never_calls_gnani(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("Gnani must not be called in a typed run")
    from backend import gnani
    monkeypatch.setattr(gnani, "transcribe", boom)
    res = rb.run(text_only=True, write=False)
    assert res["n_questions"] == 30
    assert res["speech_accuracy"] is None
    assert res["answer_accuracy"] == 1.0, res["failures"]
    assert set(res["by_language"]) == {"Hinglish", "Hindi", "English", "Noisy"}


def test_the_checker_catches_a_wrong_answer():
    from backend.config import TODAY
    truth = rb.Truth(TODAY)
    wrong = {"result": {"table": [{"label": "Atta", "value": 1}], "numbers": {"value": 1, "gap": 3},
                        "alerts": [{"product": "Atta"}], "causes": [], "spoken": ""}}
    for check in ("top:quantity:last_month", "total:revenue:this_week", "low:all", "gaps:all", "why:Chawal", "wastage:all"):
        assert rb.answer_problem(check, wrong, truth), check


def test_speech_similarity_uses_the_roman_wording():
    assert rb.similarity("chawal mein gap kyun hai", "चावल में गैप क्यों है", "chawal mein gap kyun hai") > 0.95
    assert rb.similarity("xyz abc", "Why is rice short", "") < 0.5
