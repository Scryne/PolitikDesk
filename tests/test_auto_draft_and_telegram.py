"""Otomatik Taslak Üretimi (Auto-Draft) ve Telegram Entegrasyon Testleri."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.config import get_settings
from politikdesk.editorial.auto_draft import process_pending_auto_drafts
from politikdesk.telegram_notifier import (
    build_x_intent_url,
    format_draft_telegram_message,
    send_draft_notification,
    send_telegram_test_message,
)

client = TestClient(app)


def test_build_x_intent_url() -> None:
    """X Web Intent URL kodlamasını test eder."""
    tweet = "TCMB faizi %50'de sabit tuttu. #Ekonomi"
    url = build_x_intent_url(tweet)
    assert url.startswith("https://twitter.com/intent/tweet?text=")
    assert "TCMB+faizi" in url or "TCMB%20faizi" in url
    assert "%23Ekonomi" in url or "#Ekonomi" in url


def test_format_draft_telegram_message() -> None:
    """Telegram HTML ve buton oluşturucuyu test eder."""
    event = {
        "id": 42,
        "title": "TÜİK Enflasyon Verisini Açıkladı <Önemli>",
        "salience_score": 75,
        "category": "ekonomi",
        "status": "strongly_corroborated",
    }
    draft = {
        "body": "TÜİK verilerine göre TÜFE yıllık %61,78 olarak gerçekleşti."
    }
    claims = [
        {"claim_text": "Enflasyon %61,78 oldu", "evidence_status": "strongly_corroborated"},
        {"claim_text": "Aylık artış %3,2", "evidence_status": "partially_corroborated"},
    ]

    msg, reply_markup = format_draft_telegram_message(
        event=event,
        draft=draft,
        claims=claims,
        public_base_url="https://politikdesk.com",
    )

    # HTML kaçış ve içerik kontrolü
    assert "&lt;Önemli&gt;" in msg
    assert "75/90" in msg
    assert "🟢 Doğrulandı" in msg
    assert "2/2 teyitli iddia" in msg
    assert "<code>TÜİK verilerine göre" in msg

    # Buton kontrolü
    buttons = reply_markup["inline_keyboard"][0]
    assert len(buttons) == 2
    assert buttons[0]["text"] == "🚀 X'te Aç ve Paylaş"
    assert "twitter.com/intent/tweet" in buttons[0]["url"]
    assert buttons[1]["text"] == "📊 Olayı İncele"
    assert buttons[1]["url"] == "https://politikdesk.com/event/42"


def test_send_draft_notification_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Telegram bildiriminin başarılı gönderimini test eder."""
    class MockResponse:
        status_code = 200
        text = '{"ok": true, "result": {"message_id": 999}}'
        def json(self):
            return {"ok": True, "result": {"message_id": 999}}

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, json):
            assert "api.telegram.org/bot123456:ABC/sendMessage" in url
            assert json["chat_id"] == "987654"
            assert "🚀 X'te Aç ve Paylaş" in str(json["reply_markup"])
            return MockResponse()

    import httpx
    monkeypatch.setattr(httpx, "Client", MockClient)

    event = {"id": 10, "title": "Test Olay", "salience_score": 50, "status": "ready"}
    draft = {"id": 5, "body": "Test tweet içeriği"}

    sent = send_draft_notification(
        event=event,
        draft=draft,
        bot_token="123456:ABC",
        chat_id="987654",
    )
    assert sent is True


def test_send_telegram_test_message_missing_token() -> None:
    """Eksik token ile test mesajı gönderimini doğrular."""
    res = send_telegram_test_message(bot_token="", chat_id="")
    assert res["success"] is False
    assert "PD_TELEGRAM_BOT_TOKEN" in res["error"]


def test_send_telegram_test_message_mock_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock başarılı test mesajını doğrular."""
    class MockResponse:
        status_code = 200
        def json(self):
            return {"ok": True, "result": {"message_id": 1001}}

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, json):
            return MockResponse()

    import httpx
    monkeypatch.setattr(httpx, "Client", MockClient)

    res = send_telegram_test_message(bot_token="mock_tok", chat_id="12345")
    assert res["success"] is True
    assert res["message_id"] == 1001


def test_process_pending_auto_drafts_pipeline_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Otomatik taslak üretim ve bildirim akışının entegrasyonunu mocklar."""
    fake_events = [
        {
            "id": 101,
            "title": "Bütçe Dengesi Fazla Verdi",
            "salience_score": 60,
            "status": "ready",
            "category": "ekonomi",
            "region": "turkiye",
        }
    ]

    monkeypatch.setattr(
        "politikdesk.editorial.auto_draft.find_pending_auto_draft_events",
        lambda limit, min_salience: fake_events,
    )
    monkeypatch.setattr(
        "politikdesk.editorial.service.can_generate",
        lambda event_id: {"allowed": True, "claim_count": 2},
    )
    monkeypatch.setattr(
        "politikdesk.editorial.service.generate_for_event",
        lambda event_id, angle, user_id, client, persist: {
            "draft_id": 777,
            "body": "Hazine nakit dengesi Temmuz ayında 40 milyar TL fazla verdi.",
            "is_grounded": True,
        },
    )
    monkeypatch.setattr(
        "politikdesk.editorial.auto_draft.send_draft_notification",
        lambda event, draft, claims=None: True,
    )
    monkeypatch.setattr(
        "politikdesk.editorial.repository.load_claims_for_generation",
        lambda event_id: [],
    )

    settings = get_settings()
    settings.telegram_bot_token = "mock_token"
    settings.telegram_chat_id = "mock_chat"
    settings.auto_draft_enabled = True

    result = process_pending_auto_drafts(limit=5)
    assert result["processed"] == 1
    assert result["drafts_created"] == 1
    assert result["telegram_sent"] == 1
    assert result["errors"] == 0


def test_api_telegram_test_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/telegram/test uç noktasını test eder."""
    monkeypatch.setattr(
        "politikdesk.telegram_notifier.send_telegram_test_message",
        lambda bot_token=None, chat_id=None: {"success": True, "message_id": 42},
    )

    token = get_settings().api_token
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    resp = client.post("/api/telegram/test", json={"bot_token": "tok", "chat_id": "123"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["message_id"] == 42


def test_api_auto_draft_trigger_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/drafts/auto-trigger uç noktasını test eder."""
    monkeypatch.setattr(
        "politikdesk.editorial.auto_draft.process_pending_auto_drafts",
        lambda limit=5, angle=None: {"processed": 2, "drafts_created": 2, "telegram_sent": 2, "errors": 0},
    )

    token = get_settings().api_token
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    resp = client.post("/api/drafts/auto-trigger", json={"limit": 5, "angle": "inform"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["drafts_created"] == 2
    assert data["telegram_sent"] == 2
