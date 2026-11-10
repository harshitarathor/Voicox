"""Home-screen numbers and the benchmark endpoint."""
import json

import pytest
from fastapi.testclient import TestClient

from backend import engine, main


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app) as c:
        yield c


def test_summary_matches_the_engine(client):
    body = client.get("/summary").json()
    con = main.get_con()
    assert body["revenue_30d"] == engine.total(con, "revenue", "last_30_days")
    assert body["units_30d"] == engine.total(con, "quantity", "last_30_days")
    assert len(body["trend"]["x"]) == len(body["trend"]["y"]) > 1
    assert [r["label"] for r in body["top"]] == list(
        engine.ranked(con, "revenue", "product", "last_30_days", 3, "desc")["label"])


def test_summary_finds_the_planted_problems(client):
    body = client.get("/summary").json()
    assert body["mismatch_count"] == 3          # Chawal, Doodh, Tel
    assert body["low_count"] == 2               # Daal, Sabun
    assert body["insight"]["product"] == "Chawal"   # the biggest gap first


def test_stock_health_adds_up(client):
    h = client.get("/summary").json()["health"]
    assert h["healthy"] + h["low"] + h["out"] == h["total"] == 10
    assert h["low"] == 2 and h["out"] == 0


def test_benchmark_is_not_available_until_it_has_been_run(client, monkeypatch, tmp_path):
    monkeypatch.setattr(main, "BENCHMARK", tmp_path / "results.json")
    assert client.get("/benchmark").json() == {"available": False}


def test_benchmark_serves_the_measured_file(client, monkeypatch, tmp_path):
    f = tmp_path / "results.json"
    f.write_text(json.dumps({"n_questions": 30, "speech_accuracy": 0.9}), encoding="utf-8")
    monkeypatch.setattr(main, "BENCHMARK", f)
    body = client.get("/benchmark").json()
    assert body["available"] is True and body["speech_accuracy"] == 0.9


def test_broken_benchmark_file_does_not_crash(client, monkeypatch, tmp_path):
    f = tmp_path / "results.json"
    f.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(main, "BENCHMARK", f)
    assert client.get("/benchmark").json() == {"available": False}


def test_week_change_is_worked_out_from_the_real_daily_numbers(client):
    from datetime import timedelta
    body = client.get("/summary").json()
    rows = [{"label": l, "value": v} for l, v in zip(body["trend"]["x"], body["trend"]["y"])]
    today = main.TODAY
    week = lambda a, b: sum(r["value"] for r in rows if a <= (today - main.date.fromisoformat(r["label"])).days <= b)
    expected = round((week(0, 6) - week(7, 13)) / week(7, 13) * 100, 1)
    assert body["revenue_week_change"] == expected
    assert len(body["units_trend"]["y"]) == len(body["trend"]["y"])


def test_week_change_gives_none_instead_of_a_guess():
    from datetime import date
    assert main.week_change([], date(2026, 10, 31)) is None
    few = [{"label": "2026-10-30", "value": 10.0}, {"label": "2026-10-29", "value": 12.0}]
    assert main.week_change(few, date(2026, 10, 31)) is None
    two_weeks = [{"label": f"2026-10-{d:02d}", "value": 100.0 if d > 24 else 50.0} for d in range(18, 32)]
    assert main.week_change(two_weeks, date(2026, 10, 31)) == 100.0


def test_sales_overview_matches_the_engine(client):
    body = client.get("/sales-overview").json()
    con = main.get_con()
    assert round(sum(body["daily"]["y"]), 2) == round(engine.total(con, "revenue", "last_30_days"), 2)
    assert [r["label"] for r in body["top"]] == list(
        engine.ranked(con, "revenue", "product", "last_30_days", 5, "desc")["label"])
    assert len(body["top"]) == len(body["slow"]) == 5
    assert body["top"][0]["value"] >= body["slow"][0]["value"]


def test_stock_overview_lists_every_product_and_agrees_with_the_summary(client):
    items = client.get("/stock-overview").json()["items"]
    assert len(items) == 10
    low = sorted(i["product"] for i in items if i["status"] == "low")
    assert low == ["Daal", "Sabun"]
    assert not [i for i in items if i["status"] == "out"]
