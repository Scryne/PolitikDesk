"""Arama sterilizasyonu ve SQL LIKE joker karakter güvenliği testleri."""

from __future__ import annotations

from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.web.search import _escape_like, search

client = TestClient(app)


def test_escape_like_unit() -> None:
    """_escape_like fonksiyonu % ve _ karakterlerini doğru kaçırmalıdır."""
    assert _escape_like("test") == "test"
    assert _escape_like("%50") == "\\%50"
    assert _escape_like("faiz_orani") == "faiz\\_orani"
    assert _escape_like("c:\\path") == "c:\\\\path"
    assert _escape_like("%_%") == "\\%\\_\\%"


def test_search_api_with_wildcards() -> None:
    """Komuta paleti arama ucu % ve _ karakterleri içeren sorgularda hata vermemelidir."""
    response = client.get("/api/search", params={"q": "%50"})
    assert response.status_code == 200
    payload = response.json()
    assert "results" in payload
    assert isinstance(payload["results"], list)

    response = client.get("/api/search", params={"q": "___"})
    assert response.status_code == 200
    payload = response.json()
    assert "results" in payload


def test_search_function_wildcards() -> None:
    """search fonksiyonu joker karakterlerle güvenli çalışmalıdır."""
    hits = search("%")
    # MIN_QUERY=2 olduğu için tek karakter arama boş liste döner
    assert hits == []

    hits_multi = search("%%")
    # İki karakterli % araması hata vermeden çalışmalıdır
    assert isinstance(hits_multi, list)
