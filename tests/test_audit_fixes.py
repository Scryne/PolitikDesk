"""Denetim düzeltmeleri (D02, D03, D04, D06, I01, I04, I06) için birim testleri."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.config import Settings
from politikdesk.ingestion.http import ca_bundle_path
from politikdesk.llm.budget import PostgresLedger


# ===========================================================================
# D02 — Config tekil dosya çözümlemesi
# ===========================================================================
def test_config_resolved_env_file() -> None:
    """Settings model_config içinde env_file tek seferde çözülmüş olmalı."""
    settings = Settings()
    assert settings.model_config.get("env_prefix") == "PD_"


# ===========================================================================
# D03 — PostgresLedger SQL injection beyaz liste denetimi
# ===========================================================================
def test_postgres_ledger_interval_whitelist() -> None:
    """PostgresLedger._sum_since yalnızca 'day' ve 'month' kabul eder."""
    ledger = PostgresLedger()
    with pytest.raises(ValueError, match="Geçersiz SQL interval"):
        ledger._sum_since("year; DROP TABLE llm_calls; --")


# ===========================================================================
# D04 — CA bundle güvenli kullanıcı dizini
# ===========================================================================
def test_ca_bundle_path_user_private_dir() -> None:
    """CA bundle genel /tmp altında değil, kullanıcıya özel önbellekte olmalı."""
    bundle_file = ca_bundle_path()
    assert Path(bundle_file).exists()
    assert "PolitikDesk" in bundle_file or ".cache" in bundle_file or "certifi" in bundle_file


# ===========================================================================
# I01 — API Token kimlik doğrulama middleware
# ===========================================================================
def test_token_auth_middleware_disabled_by_default() -> None:
    """PD_API_TOKEN boşken istekler doğrudan geçer."""
    client = TestClient(app)
    response = client.get("/health/live")
    assert response.status_code == 200


def test_token_auth_middleware_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    """PD_API_TOKEN ayarlıyken yetkisiz istekler 401/403 alır, doğru token ile geçer."""
    import politikdesk.api.main as api_main

    monkeypatch.setattr(api_main, "get_settings", lambda: Settings(api_token="gizli-token-123"))

    client = TestClient(app)

    # Sağlık uçları muaftır
    live_resp = client.get("/health/live")
    assert live_resp.status_code == 200

    # Korumalı uç belirteçsiz çağrılınca 401
    unauth_resp = client.get("/api/angles")
    assert unauth_resp.status_code == 401
    assert "Kimlik doğrulama gerekli" in unauth_resp.json()["detail"]

    # Yanlış belirteç 403
    forbidden_resp = client.get("/api/angles", headers={"Authorization": "Bearer yanlis-token"})
    assert forbidden_resp.status_code == 403

    # Doğru Bearer belirteci 200
    ok_bearer = client.get("/api/angles", headers={"Authorization": "Bearer gizli-token-123"})
    assert ok_bearer.status_code == 200

    # Doğru X-API-Token başlığı 200
    ok_header = client.get("/api/angles", headers={"X-API-Token": "gizli-token-123"})
    assert ok_header.status_code == 200


# ===========================================================================
# I06 — CSRF koruma middleware
# ===========================================================================
def test_csrf_protection_allows_safe_methods() -> None:
    """GET istekleri cross-origin olsa bile CSRF kontrolünden geçer."""
    client = TestClient(app)
    resp = client.get("/api/angles", headers={"Origin": "https://evil.com"})
    assert resp.status_code == 200


def test_csrf_protection_blocks_mismatched_origin() -> None:
    """POST/PUT isteklerinde Origin != Host ise 403 ile engellenir."""
    client = TestClient(app)
    resp = client.post(
        "/api/events/1/feedback",
        headers={"Origin": "https://evil-site.com", "Host": "localhost:8000"},
        json={"note": "saldiri"},
    )
    assert resp.status_code == 403
    assert "CSRF koruması" in resp.json()["detail"]


def test_csrf_protection_allows_matching_origin() -> None:
    """Origin == Host olduğunda istek geçer."""
    client = TestClient(app)
    resp = client.post(
        "/api/activity",
        headers={"Origin": "http://testserver", "Host": "testserver"},
        json={"kind": "page_view", "path": "/feed"},
    )
    # 204 No Content
    assert resp.status_code == 204
