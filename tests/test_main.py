from concurrent.futures import ThreadPoolExecutor

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend import engine, insights, main
from backend.pipeline import load_all
from backend.schemas import StructuredQuery


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app) as c:            # runs startup and shutdown
        yield c


def ask(client, **body):
    return client.post("/ask", json=body)


# ---------- health ----------
def test_health_and_ready(client):
    assert client.get("/health").json()["ok"] is True
    r = client.get("/ready").json()
    assert r["ready"] is True and r["rows"]["inventory"] == 10


def test_home_without_frontend_still_answers(client):
    assert client.get("/").status_code == 200


# ---------- input checks ----------
def test_empty_question_is_rejected_politely(client):
    for body in ({"text": ""}, {"text": "   "}, {}):
        r = ask(client, **body).json()
        assert r["status"] == "reject" and r["message"]


def test_text_and_query_together_are_refused(client):
    assert ask(client, text="hello", query={"intent": "low_stock"}).status_code == 422


def test_very_long_text_is_refused(client):
    assert ask(client, text="a" * 1001).status_code == 422


def test_unsupported_question_gets_a_helpful_reject(client):
    r = ask(client, text="Weather kaisa hai").json()
    assert r["status"] == "reject" and "poochhiye" in r["message"]


def test_invalid_structured_query_is_rejected(client):
    assert ask(client, query={"intent": "delete_all"}).json()["status"] == "reject"
    assert ask(client, query={"intent": "total", "sql": "DROP TABLE sales"}).json()["status"] == "reject"


def test_unknown_product_needs_clarification(client):
    r = ask(client, query={"intent": "total", "product": "laptop"}).json()
    assert r["status"] == "clarify" and r["result"] is None


def test_explain_without_a_product_asks_which(client):
    r = ask(client, query={"intent": "explain_gap"}).json()
    assert r["status"] == "clarify" and "product" in r["message"]


# ---------- confirm flow ----------
def test_near_match_asks_then_runs_once_confirmed(client):
    r = ask(client, text="Chawl ki sales kitni hui").json()
    assert r["status"] == "confirm" and r["query"]["product"] == "Chawal" and r["result"] is None
    again = ask(client, query=r["query"], confirmed=True).json()
    assert again["status"] == "ok" and "Chawal" in again["result"]["spoken"]


def test_confirmed_flag_does_not_bypass_validation(client):
    bad = {"intent": "total", "product": "laptop"}
    assert ask(client, query=bad, confirmed=True).json()["status"] == "clarify"


# ---------- answers carry the engine's numbers ----------
def test_total_sales_today(client):
    con, _ = load_all()
    expected = engine.total(con, "revenue", "today")
    r = ask(client, text="Aaj ki total sales kitni hui?").json()
    assert r["status"] == "ok"
    assert r["result"]["numbers"]["value"] == expected
    assert main._say(expected) in r["result"]["spoken"]
    assert r["result"]["numbers"]["display"] == f"₹{main._commas(expected)}"


def test_quantity_wording_is_clean(client):
    r = ask(client, text="Rice kitna bika aaj").json()["result"]["spoken"]
    assert r.startswith("Aaj Chawal") and "unit bika" in r and "(unit)" not in r


def test_top_product_last_month(client):
    r = ask(client, text="Pichle mahine sabse zyada kya bika?").json()
    assert r["status"] == "ok"
    assert "Biscuit" in r["result"]["spoken"] and "434" in r["result"]["spoken"]
    assert r["result"]["chart"]["type"] == "bar"


def test_one_question_gets_one_answer_a_list_question_gets_a_list(client):
    one = ask(client, text="Pichle mahine sabse zyada kya bika?").json()
    assert one["query"]["limit"] == 1 and "sabse zyada Biscuit bika" in one["result"]["spoken"]
    many = ask(client, text="Sabse kam bikne wale products kaun se hain?").json()
    assert many["query"]["limit"] == 5 and many["query"]["order"] == "asc"
    three = ask(client, text="Last month top 3 products by revenue").json()
    assert three["query"]["limit"] == 3


def test_compare_and_trend(client):
    c = ask(client, text="Is hafte ki bikri pichle hafte se kaisi rahi?").json()["result"]
    assert c["numbers"]["period_a"] == "this_week" and "percent" in c["spoken"]
    t = ask(client, text="Chawal ka trend dikhao").json()["result"]
    assert t["chart"]["type"] == "line" and "ko hua" in t["spoken"]


def test_low_stock_gaps_and_wastage(client):
    assert "Daal" in ask(client, text="Kaunsa stock kam hai?").json()["result"]["spoken"]
    gaps = ask(client, text="Kahan stock mismatch hai?").json()["result"]
    assert "Chawal mein 17 unit" in gaps["spoken"] and len(gaps["alerts"]) == 3
    waste = ask(client, text="Kharab maal kitna hai").json()["result"]["spoken"]
    assert "Doodh" in waste


def test_every_result_has_the_same_fields(client):
    keys = {"intent", "spoken", "numbers", "table", "chart", "causes", "alerts", "disclaimer"}
    for text in ["Aaj ki total sales kitni hui?", "Kahan stock mismatch hai?",
                 "Chawal mein gap kyun hai?", "Kharab maal kitna hai"]:
        assert set(ask(client, text=text).json()["result"]) == keys


# ---------- the "Why?" explainer on the planted data ----------
def test_chawal_gap_points_to_the_missing_day(client):
    r = ask(client, text="Chawal mein gap kyun hai?").json()["result"]
    assert r["causes"][0]["rule"] == "no_sales_day" and "11 Oct" in r["spoken"]
    assert r["disclaimer"]


def test_planted_unexplained_gaps_are_not_blamed_on_missing_days(client):
    for text in ("Tel mein gap kyun hai?", "Doodh mein gap kyun hai?"):
        r = ask(client, text=text).json()["result"]
        assert "no_sales_day" not in [c["rule"] for c in r["causes"]], text


# ---------- panels and report ----------
def test_fixed_panels_and_data_report(client):
    assert client.get("/stock-gaps").json()["result"]["intent"] == "stock_gap"
    assert "Daal" in client.get("/low-stock").json()["result"]["spoken"]
    rep = client.get("/data-report").json()
    assert rep["report"]["rows_rejected"] == 13 and len(rep["report"]["rejected_rows"]) == 13


# ---------- failures ----------
def test_database_failure_gives_a_controlled_error(client, monkeypatch):
    def boom(con, q):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(main, "run_query", boom)
    r = ask(client, text="Aaj ki total sales kitni hui?")
    assert r.status_code == 500
    body = r.json()
    assert body["status"] == "error" and "secret" not in str(body)


def test_period_with_no_records_is_not_reported_as_zero_sales():
    con = duckdb.connect()
    con.execute("CREATE TABLE sales AS SELECT DATE '2026-01-01' AS date, 'Chawal' AS product, "
                "'Grocery' AS category, 5 AS quantity, 300.0 AS revenue")
    out = main.run_query(con, StructuredQuery(intent="total", period="today"))
    assert "koi sales data nahi" in out["spoken"]
    out = main.run_query(con, StructuredQuery(intent="compare", period="today", compare_period="yesterday"))
    assert "koi sales data nahi" in out["spoken"]


def test_unsupported_intent_is_refused():
    q = StructuredQuery(intent="total").model_copy(update={"intent": "something_new"})
    with pytest.raises(ValueError):
        main.run_query(duckdb.connect(), q)


# ---------- several requests at once ----------
def test_parallel_requests_all_succeed(client):
    questions = ["Aaj ki total sales kitni hui?", "Kaunsa stock kam hai?",
                 "Kahan stock mismatch hai?", "Pichle mahine sabse zyada kya bika?"] * 5
    with ThreadPoolExecutor(8) as pool:
        replies = list(pool.map(lambda t: ask(client, text=t).json(), questions))
    assert all(r["status"] == "ok" for r in replies)