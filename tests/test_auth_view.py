"""Kimlik doğrulama ve /login arayüzü testleri (F1 / I01)."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_login_page_renders_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Token ayarlı iken /login sayfası doğru şekilde HTML üretir."""
    monkeypatch.setenv("PD_API_TOKEN", "gizli-token-123")
    get_settings.cache_clear()
    client = TestClient(app)

    resp = client.get("/login?next=/feed")
    assert resp.status_code == 200
    assert "PolitikDesk" in resp.text
    assert "Giriş Yap" in resp.text
    assert "PD_API_TOKEN" in resp.text


def test_login_page_post_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Doğru token post edildiğinde 303 ile yönlendirir ve pd_token çerezi ayarlar."""
    monkeypatch.setenv("PD_API_TOKEN", "gizli-token-123")
    get_settings.cache_clear()
    client = TestClient(app)

    resp = client.post("/login", data={"token": "gizli-token-123", "next": "/feed"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/feed"
    assert "pd_token=gizli-token-123" in resp.headers.get("set-cookie", "")


def test_login_page_post_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hatalı token girildiğinde 401 ve hata mesajı gösterir."""
    monkeypatch.setenv("PD_API_TOKEN", "gizli-token-123")
    get_settings.cache_clear()
    client = TestClient(app)

    resp = client.post("/login", data={"token": "yanlis-token", "next": "/feed"}, follow_redirects=False)
    assert resp.status_code == 401
    assert "belirteci geçersiz" in resp.text


def test_browser_unauthenticated_redirects_to_login(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tarayıcıdan (Accept: text/html) korumalı sayfaya gelen yetkisiz istek /login'e yönlendirilir."""
    monkeypatch.setenv("PD_API_TOKEN", "gizli-token-123")
    get_settings.cache_clear()
    client = TestClient(app)

    resp = client.get("/feed", headers={"Accept": "text/html,application/xhtml+xml"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/login?next=")


def test_cookie_authentication_grants_access(monkeypatch: pytest.MonkeyPatch) -> None:
    """pd_token çerezi olan istek korumalı sayfaya erişebilir."""
    monkeypatch.setenv("PD_API_TOKEN", "gizli-token-123")
    get_settings.cache_clear()
    client = TestClient(app, cookies={"pd_token": "gizli-token-123"})

    resp = client.get("/feed")
    assert resp.status_code == 200
    assert "feed-grid" in resp.text or "PolitikDesk" in resp.text


def test_query_token_authenticates_and_sets_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    """URL'de ?token=... ile gelen istek oturumu doğrular ve çerez yazar."""
    monkeypatch.setenv("PD_API_TOKEN", "gizli-token-123")
    get_settings.cache_clear()
    client = TestClient(app)

    resp = client.get("/feed?token=gizli-token-123", follow_redirects=False)
    assert resp.status_code == 200
    assert "pd_token=gizli-token-123" in resp.headers.get("set-cookie", "")


def test_logout_clears_cookie() -> None:
    """/logout çerezi siler ve /login'e yönlendirir."""
    client = TestClient(app)
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
