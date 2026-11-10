"""Asking how much stock an item has must answer with stock, never with sales."""
import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.extractor import extract


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app) as c:
        yield c


@pytest.mark.parametrize("text, product", [
    ("Daal ka stock kitna hai", "Daal"),
    ("Chawal kitna bacha hai", "Chawal"),
    ("how much rice stock is left", "Chawal"),
])
def test_stock_level_questions_are_low_stock_intent(text, product):
    q = extract(text)
    assert q.intent == "low_stock" and q.product == product


def test_a_low_item_is_reported_as_low(client):
    spoken = client.post("/ask", json={"text": "Daal ka stock kitna hai"}).json()["result"]["spoken"]
    assert "Daal" in spoken and "kam hai" in spoken and "134" in spoken


def test_a_healthy_item_gets_its_numbers(client):
    spoken = client.post("/ask", json={"text": "Chawal ka stock kitna hai"}).json()["result"]["spoken"]
    assert "Chawal ka stock theek hai" in spoken and "177" in spoken


def test_selling_questions_are_not_taken_for_stock(client):
    spoken = client.post("/ask", json={"text": "Chawal ki bikri pichle mahine kitni thi"}).json()["result"]["spoken"]
    assert "bikri" in spoken
