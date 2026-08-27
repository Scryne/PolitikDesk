"""tests/test_export_and_api.py — Dışa Aktarma ve Yeni API Uçları Testleri."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from politikdesk.api.main import app

client = TestClient(app)


def test_export_event_markdown():
    mock_data = {
        "event": {
            "id": 1,
            "title": "TCMB Politika Faizini %50 Seviyesinde Sabit Bıraktı",
            "salience_score": 85,
            "status": "developing",
            "has_primary_source": True,
            "independence_groups": 3,
        },
        "claims": [
            {
                "id": 10,
                "claim_text": "Politika faizi yüzde 50 olarak sabit tutuldu",
                "evidence_status": "strongly_corroborated",
                "claim_type": "number",
                "evidence_count": 4,
            }
        ],
        "articles": [
            {
                "source_name": "TCMB",
                "tier": "T1",
                "kind": "official",
                "title": "PPK Karar Metni",
                "slug": "tcmb",
            }
        ],
    }

    with patch("politikdesk.web.repository.event_page", return_value=mock_data):
        res = client.get("/api/events/1/export?format=markdown")
        assert res.status_code == 200
        assert "POLİTİKDESK" in res.text.upper() or "TCMB" in res.text
        assert "Doğrulanmış İddialar" in res.text
        assert "TCMB" in res.text


def test_export_event_text():
    mock_data = {
        "event": {
            "id": 2,
            "title": "TÜİK Enflasyon Verisini Açıkladı",
            "salience_score": 75,
        },
        "claims": [
            {
                "id": 20,
                "claim_text": "Aylık enflasyon yüzde 2.47 oldu",
                "evidence_status": "strongly_corroborated",
                "claim_type": "number",
            }
        ],
        "articles": [{"source_name": "TÜİK", "tier": "T1", "kind": "official", "slug": "tuik"}],
    }

    with patch("politikdesk.web.repository.event_page", return_value=mock_data):
        res = client.get("/api/events/2/export?format=text")
        assert res.status_code == 200
        assert "POLİTİKDESK KANIT DOSYASI" in res.text
        assert "Aylık enflasyon" in res.text


def test_get_event_blindspot_endpoint():
    mock_data = {
        "event": {"id": 3, "title": "Bütçe Dengesi Raporu"},
        "claims": [],
        "articles": [
            {"source_name": "hazine", "tier": "T1", "slug": "hazine"},
            {"source_name": "bloomberght", "tier": "T2", "slug": "bloomberght"},
        ],
    }

    with patch("politikdesk.web.repository.event_page", return_value=mock_data):
        res = client.get("/api/events/3/blindspot")
        assert res.status_code == 200
        data = res.json()
        assert data["event_id"] == 3
        assert "tier_breakdown" in data
        assert "severity" in data
        assert data["covered_count"] >= 2


def test_get_stance_shifts_api():
    mock_shifts = [
        {
            "actor_name": "Mehmet Şimşek",
            "shift_type": "broken_promise",
            "topic_or_metric": "Enflasyon",
            "earlier_event_id": 1,
            "earlier_event_title": "Hedef",
            "earlier_claim_text": "Hedef %20",
            "earlier_date": "2026-01-01",
            "later_event_id": 2,
            "later_event_title": "Gerçekleşen",
            "later_claim_text": "Gerçekleşen %45",
            "later_date": "2026-06-01",
            "time_span_days": 150,
            "confidence": 0.90,
            "evidence_summary": "Çelişki",
            "metadata": {},
        }
    ]

    with patch(
        "politikdesk.political_memory.service.list_all_stance_shifts", return_value=mock_shifts
    ):
        res = client.get("/api/memory/stance-shifts")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["actor_name"] == "Mehmet Şimşek"


def test_export_event_svg_and_card_endpoint():
    mock_data = {
        "event": {
            "id": 5,
            "title": "TCMB Faiz Kararını Açıkladı",
            "salience_score": 88,
            "independence_groups": 3,
        },
        "claims": [
            {
                "id": 50,
                "claim_text": "Politika faizi yüzde 50 olarak teyit edildi",
                "evidence_status": "strongly_corroborated",
                "claim_type": "number",
            }
        ],
        "articles": [{"source_name": "TCMB", "tier": "T1", "kind": "official", "slug": "tcmb"}],
    }

    with patch("politikdesk.web.repository.event_page", return_value=mock_data):
        # 1. /export?format=svg
        res_export = client.get("/api/events/5/export?format=svg")
        assert res_export.status_code == 200
        assert "image/svg+xml" in res_export.headers["content-type"]
        assert "<svg" in res_export.text
        assert "POLİTİKDESK" in res_export.text
        assert "GÜÇLÜ TEYİTLİ" in res_export.text

        # 2. /evidence-card.svg (16:9 landscape default)
        res_card = client.get("/api/events/5/evidence-card.svg")
        assert res_card.status_code == 200
        assert "image/svg+xml" in res_card.headers["content-type"]
        assert "<svg" in res_card.text
        assert "TCMB Faiz Kararını Açıkladı" in res_card.text
        assert 'viewBox="0 0 800 450"' in res_card.text

        # 3. /evidence-card.svg (1:1 square)
        res_card_square = client.get("/api/events/5/evidence-card.svg?ratio=1:1")
        assert res_card_square.status_code == 200
        assert 'viewBox="0 0 800 800"' in res_card_square.text
        assert "TEYİT HAVUZU VE METRİK DAĞILIMI" in res_card_square.text
