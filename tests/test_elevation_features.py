"""PolitikDesk yükseltme ve yeni ürün özellikleri testleri.

1. Parliamentary Stance Diff API
2. Macro Anomaly Alerting & Webhook Dispatcher
3. Test DB Fail-Closed İzolasyonu
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from politikdesk.analysis.anomaly_alerts import (
    MacroAnomalyAlert,
    dispatch_anomaly_alert,
    format_alert_payload,
)
from politikdesk.api.main import app

client = TestClient(app)


def test_format_alert_payload_formats() -> None:
    """Anomali uyarı formatlayıcısı Discord, Slack ve generic formatları doğru üretmelidir."""
    alert = MacroAnomalyAlert(
        alert_id="alt-12345",
        series_key="usd_try",
        series_label="USD/TRY Kuru",
        current_value=34.50,
        previous_value=33.20,
        change_pct=3.91,
        severity="high",
        score=4.25,
        detected_at=datetime.now(UTC).isoformat(),
        summary="USD/TRY kurunda %3.91 oranında sert yükseliş tespit edildi.",
    )

    # Generic JSON
    gen = format_alert_payload(alert, format_type="generic")
    assert gen["event"] == "macro_anomaly_alert"
    assert gen["alert"]["series_key"] == "usd_try"
    assert gen["alert"]["current_value"] == 34.50

    # Discord Embed
    disc = format_alert_payload(alert, format_type="discord")
    assert "embeds" in disc
    assert len(disc["embeds"]) == 1
    assert disc["embeds"][0]["title"] == "🚨 Makro Anomali: USD/TRY Kuru"
    assert disc["embeds"][0]["color"] == 0xE74C3C

    # Slack Block
    slack = format_alert_payload(alert, format_type="slack")
    assert "blocks" in slack
    assert slack["blocks"][0]["type"] == "header"
    assert "USD/TRY Kuru" in slack["blocks"][0]["text"]["text"]


def test_dispatch_anomaly_alert_success() -> None:
    """dispatch_anomaly_alert geçerli bir 200/204 yanıtında True dönmelidir."""
    alert = MacroAnomalyAlert(
        alert_id="alt-test",
        series_key="policy_rate",
        series_label="TCMB Politika Faizi",
        current_value=50.0,
        previous_value=45.0,
        change_pct=11.11,
        severity="critical",
        score=5.0,
        detected_at=datetime.now(UTC).isoformat(),
        summary="Faiz artırımı gerçekleşti.",
    )

    with patch("politikdesk.ingestion.http.HttpClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=204)
        success = dispatch_anomaly_alert(
            alert, "https://discord.com/api/webhooks/test/123", format_type="discord"
        )
        assert success is True
        mock_post.assert_called_once()


def test_api_stance_diff_endpoint() -> None:
    """`/api/stance/diff` endpoint'i doğru sözleşme ile yanıt vermelidir."""
    response = client.get("/api/stance/diff")
    assert response.status_code == 200
    payload = response.json()
    assert "count" in payload
    assert "shifts" in payload
    assert isinstance(payload["shifts"], list)


def test_api_anomalies_feature_flag_disabled_by_default() -> None:
    """Makro anomali uçları varsayılan olarak 403 Forbidden ile reddedilmelidir."""
    resp_alerts = client.get("/api/anomalies/alerts")
    assert resp_alerts.status_code == 403
    assert "devre dışı" in resp_alerts.json()["detail"]

    resp_dispatch = client.post(
        "/api/anomalies/dispatch-test",
        json={"webhook_url": "https://discord.com/api/webhooks/test"},
    )
    assert resp_dispatch.status_code == 403
    assert "devre dışı" in resp_dispatch.json()["detail"]


def test_api_anomalies_alerts_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """`/api/anomalies/alerts` endpoint'i aktif anomali listesini dönmelidir."""
    from politikdesk.config import get_settings

    monkeypatch.setattr(get_settings(), "enable_anomaly_alerts", True)
    response = client.get("/api/anomalies/alerts")
    assert response.status_code == 200
    payload = response.json()
    assert "count" in payload
    assert "alerts" in payload
    assert isinstance(payload["alerts"], list)


def test_api_anomalies_dispatch_test_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """`/api/anomalies/dispatch-test` endpoint'i webhook testini tetikleyebilmelidir."""
    from politikdesk.config import get_settings

    monkeypatch.setattr(get_settings(), "enable_anomaly_alerts", True)
    with patch("politikdesk.ingestion.http.HttpClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        response = client.post(
            "/api/anomalies/dispatch-test",
            json={
                "webhook_url": "https://hooks.slack.com/services/test/123",
                "format_type": "slack",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert "alert" in payload


def test_test_dsn_fail_closed_on_production_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """PD_ENV='production' olduğunda test koşumu derhal reddedilmelidir."""
    from tests.conftest import _get_test_dsn

    monkeypatch.setenv("PD_ENV", "production")
    with pytest.raises(pytest.fail.Exception, match="KRİTİK GÜVENLİK İHLALİ"):
        _get_test_dsn()


def test_test_dsn_fail_closed_on_prod_keyword(monkeypatch: pytest.MonkeyPatch) -> None:
    """DSN içinde 'prod' veya 'production' geçtiğinde test koşumu derhal durdurulmalıdır."""
    from tests.conftest import _get_test_dsn

    monkeypatch.setenv("PD_ENV", "test")
    monkeypatch.setenv(
        "PD_TEST_DATABASE_URL", "postgresql://user:pass@prod-db.politikdesk.internal:5432/pd_live"
    )
    with pytest.raises(pytest.fail.Exception, match="KRİTİK GÜVENLİK İHLALİ"):
        _get_test_dsn()


def test_dispatch_anomaly_alert_blocks_ssrf() -> None:
    """dispatch_anomaly_alert yerel IP veya metadata adreslerine SSRF saldırılarını engellemelidir."""
    alert = MacroAnomalyAlert(
        alert_id="alt-ssrf",
        series_key="usd_try",
        series_label="USD/TRY",
        current_value=34.0,
        previous_value=33.0,
        change_pct=3.0,
        severity="high",
        score=3.5,
        detected_at=datetime.now(UTC).isoformat(),
        summary="Test",
    )

    # Loopback IP
    assert dispatch_anomaly_alert(alert, "http://127.0.0.1:8000/admin") is False
    # Link-local / Cloud Metadata
    assert dispatch_anomaly_alert(alert, "http://169.254.169.254/latest/meta-data") is False
    # Localhost
    assert dispatch_anomaly_alert(alert, "http://localhost:5432") is False
    # RFC 6598 CGNAT
    assert dispatch_anomaly_alert(alert, "http://100.64.0.1:8000/webhook") is False
    assert dispatch_anomaly_alert(alert, "http://100.127.255.254:9000/hook") is False
    # IPv4-mapped IPv6 CGNAT
    assert dispatch_anomaly_alert(alert, "http://[::ffff:100.64.0.1]:8000/hook") is False


def test_api_anomalies_dispatch_test_blocks_cgnat_ssrf(monkeypatch: pytest.MonkeyPatch) -> None:
    """`/api/anomalies/dispatch-test` CGNAT ve internal adreslere istek atmayı reddetmelidir."""
    from politikdesk.config import get_settings

    monkeypatch.setattr(get_settings(), "enable_anomaly_alerts", True)
    response = client.post(
        "/api/anomalies/dispatch-test",
        json={
            "webhook_url": "http://100.64.0.1:8080/cgnat-hook",
            "format_type": "generic",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
