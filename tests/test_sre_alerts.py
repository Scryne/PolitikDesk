"""SRE Webhook Alarm Motoru Testleri."""

from __future__ import annotations

import httpx
import pytest

from politikdesk.sre_alerts import (
    _RECENT_ALERTS,
    format_discord_payload,
    format_generic_payload,
    format_slack_payload,
    format_telegram_payload,
    send_alert_notification,
)


@pytest.fixture(autouse=True)
def _clear_alert_cooldown():
    _RECENT_ALERTS.clear()
    yield
    _RECENT_ALERTS.clear()


def test_format_discord_payload() -> None:
    payload = format_discord_payload(
        title="Boru Hattı Tıkandı",
        detail="İddia çıkarımı aşamasında 250 öğe bekliyor",
        severity="CRITICAL",
        source="pipeline_health",
        action="pd start",
    )
    assert "embeds" in payload
    embed = payload["embeds"][0]
    assert "Boru Hattı Tıkandı" in embed["title"]
    assert embed["color"] == 15682628
    assert len(embed["fields"]) == 4


def test_format_slack_payload() -> None:
    payload = format_slack_payload(
        title="LLM Bütçe Uyarısı",
        detail="Günlük limit %90 aşıldı",
        severity="WARNING",
        source="budget_guard",
        action="Limit artırın",
    )
    assert "blocks" in payload
    assert "LLM Bütçe Uyarısı" in payload["text"]


def test_format_telegram_payload() -> None:
    payload = format_telegram_payload(
        title="Konteyner Çöktü",
        detail="pd-worker-llm yanıt vermiyor",
        severity="CRITICAL",
        source="watchdog",
        action="docker restart",
    )
    assert "<b>" in payload["text"]
    assert payload["parse_mode"] == "HTML"


def test_format_generic_payload() -> None:
    payload = format_generic_payload(
        title="Bilgi",
        detail="DR tatbikatı tamamlandı",
        severity="INFO",
        source="dr_drill",
        action="",
    )
    assert payload["service"] == "politikdesk"
    assert payload["severity"] == "INFO"


def test_send_alert_notification_unconfigured() -> None:
    """Webhook URL ayarlı değilse sessizce False döner."""
    sent = send_alert_notification("Test", "Ayrıntı", webhook_url="")
    assert sent is False


def test_send_alert_notification_mock_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock httpx Client ile başarılı gönderim."""
    def mock_post(self, url, **kwargs):
        req = httpx.Request("POST", url)
        return httpx.Response(204, request=req)

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    sent = send_alert_notification(
        title="Test Alarmı",
        detail="Detay",
        severity="WARNING",
        source="unit_test",
        webhook_url="https://discord.com/api/webhooks/123/abc",
        force=True,
    )
    assert sent is True


def test_send_alert_notification_cooldown_suppression(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aynı alarm 5 dakika içinde tekrar gönderilmez."""
    def mock_post(self, url, **kwargs):
        req = httpx.Request("POST", url)
        return httpx.Response(200, request=req)

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    # 1. Gönderim başarılı
    sent1 = send_alert_notification(
        title="Aynı Alarm",
        detail="Detay",
        severity="CRITICAL",
        source="cooldown_test",
        webhook_url="https://hooks.slack.com/services/123",
    )
    assert sent1 is True

    # 2. Gönderim cooldown nedeniyle engellenir
    sent2 = send_alert_notification(
        title="Aynı Alarm",
        detail="Detay",
        severity="CRITICAL",
        source="cooldown_test",
        webhook_url="https://hooks.slack.com/services/123",
    )
    assert sent2 is False

    # force=True ile bypass edilir
    sent3 = send_alert_notification(
        title="Aynı Alarm",
        detail="Detay",
        severity="CRITICAL",
        source="cooldown_test",
        webhook_url="https://hooks.slack.com/services/123",
        force=True,
    )
    assert sent3 is True
