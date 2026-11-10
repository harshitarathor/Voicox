"""The frontend is plain files served by FastAPI: every file index.html and the CSS point to must exist."""
import re

import pytest
from fastapi.testclient import TestClient

from backend import main


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app) as c:
        yield c


def test_home_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "<title>Voicox</title>" in r.text


def test_every_linked_file_exists(client):
    html = client.get("/").text
    links = re.findall(r'(?:href|src)="(/static/[^"]+)"', html)
    assert len(links) >= 6                                   # one stylesheet and five scripts
    for link in links:
        assert client.get(link).status_code == 200, link


def test_css_images_exist(client):
    css = client.get("/static/css/styles.css").text
    images = re.findall(r"url\(\.\./(assets/[^)]+)\)", css)
    assert images and "base64" not in css
    for image in images:
        assert client.get("/static/" + image).status_code == 200, image


def test_every_page_has_its_own_file_and_registers_itself(client):
    for name in ("ask", "sales", "stock", "detective", "data", "quality"):
        r = client.get(f"/static/js/pages/{name}.js")
        assert r.status_code == 200, name
        assert f"P.{name} = " in r.text