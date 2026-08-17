"""Yeni eklenen Çok Kanallı İhracat ve Haber Masası Kumanda Odası testleri."""

from __future__ import annotations

from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.web.export_formats import (
    to_audio_script,
    to_instant_dispatch,
    to_linkedin_brief,
    to_x_thread,
)


def test_export_formats_generators() -> None:
    ev = {"id": 42, "title": "TCMB Politika Faizini %50 Seviyesinde Sabit Bıraktı", "salience_score": 75}
    claims = [
        {"claim_text": "Para Politikası Kurulu faizi değiştirmeme kararı aldı.", "evidence_status": "strongly_corroborated"},
        {"claim_text": "Enflasyon beklentilerinde belirgin bir düşüş gözlendi.", "evidence_status": "partially_corroborated"},
    ]
    articles = [
        {"source_name": "TCMB Resmî", "tier": 1},
        {"source_name": "Bloomberg HT", "tier": 2},
    ]

    # 1. X Thread
    tweets = to_x_thread(ev, claims, articles)
    assert len(tweets) >= 3
    for t in tweets:
        assert len(t) <= 280, f"Tweet 280 karakteri aşıyor: {len(t)}"

    # 2. LinkedIn Brief
    li = to_linkedin_brief(ev, claims, articles)
    assert "MAKRO GÜNDEM ÖZETİ" in li
    assert "TCMB Resmî" in li

    # 3. Instant Dispatch
    inst = to_instant_dispatch(ev, claims, articles)
    assert "POLİTİKDESK ANLIK BÜLTEN" in inst

    # 4. Audio Script
    audio = to_audio_script(ev, claims, articles)
    assert "PolitikDesk hızlı gündem bülteni" in audio


def test_war_room_endpoint() -> None:
    client = TestClient(app)
    res = client.get("/war-room")
    assert res.status_code == 200
    assert "Haber Masası" in res.text
    assert "Kumanda Odası" in res.text
    assert "wr-live-dot" in res.text
