"""Doğruluk İnfografik Kartı (SVG) Testleri."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.config import get_settings
from politikdesk.editorial.infographics import generate_event_svg_card, render_event_card_svg


def test_generate_event_svg_card_content() -> None:
    event = {
        "id": 42,
        "title": "TCMB Politika Faizini Yüzde 50'de Sabit Tuttu",
        "category": "ekonomi",
        "category_label": "Ekonomi",
        "displayed_salience": 92,
        "first_reported_at": "2026-08-20T10:00:00Z",
    }
    claims = [
        {
            "claim_text": "TCMB politika faizini değiştirmeyerek %50 seviyesinde bıraktı.",
            "evidence_status": "strongly_corroborated",
            "speaker": "TCMB PPK",
            "evidence": [
                {"source_name": "TCMB", "tier": 1},
                {"source_name": "Resmî Gazete", "tier": 1},
            ],
        }
    ]

    svg = generate_event_svg_card(event, claims)
    assert "<svg" in svg
    assert "</svg>" in svg
    assert "POLITIK" in svg
    assert "TEYİTLİ &amp; DOĞRULANDI" in svg or "TEYİTLİ" in svg
    assert "TCMB" in svg
    assert "viewBox=\"0 0 1200 675\"" in svg


def test_generate_event_svg_card_contradicted() -> None:
    event = {
        "id": 99,
        "title": "Enflasyon Tahmin Açıklaması",
        "category": "siyaset",
    }
    claims = [
        {
            "claim_text": "Enflasyon yıl sonu %20 olacak",
            "evidence_status": "contradicted",
            "speaker": "Bakan",
        }
    ]
    svg = generate_event_svg_card(event, claims)
    assert "ÇELİŞKİLİ BEYAN" in svg


def test_event_card_svg_endpoint_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.api_token}"} if settings.api_token else {}
    client = TestClient(app)

    import politikdesk.web.repository as repo
    monkeypatch.setattr(
        repo,
        "event_page",
        lambda event_id, user_id: {
            "event": {"id": event_id, "title": "Test Olayı", "category": "ekonomi"},
            "claims": [{"claim_text": "Test iddiası", "evidence_status": "strongly_corroborated"}],
        },
    )

    res = client.get("/api/events/42/card.svg", headers=headers)
    assert res.status_code == 200
    assert "image/svg+xml" in res.headers.get("content-type", "")
    assert "<svg" in res.text

    # render_event_card_svg doğrudan çağrısı
    card_svg = render_event_card_svg(42)
    assert card_svg is not None
    assert "<svg" in card_svg
