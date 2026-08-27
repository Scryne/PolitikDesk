"""Omnichannel Çoklu Platform Yayın Formatlayıcı ve Dejavu Koruması Testleri."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.editorial.omnichannel import (
    OmnichannelPackage,
    RepetitionAlert,
    build_omnichannel_package_from_event,
    check_anti_repetition,
    format_linkedin_post,
    format_newsletter_markdown,
    format_telegram_note,
    format_x_thread,
)

client = TestClient(app)


def test_format_x_thread_generation() -> None:
    """X thread formatlayıcı testi."""
    claims = [
        {
            "claim_text": "TCMB politika faizini %50 seviyesinde sabit tuttu",
            "speaker": "TCMB",
            "evidence_status": "strongly_corroborated",
            "source": "TCMB",
        },
        {
            "claim_text": "Yıllık enflasyon beklentisi %38 olarak korundu",
            "speaker": "Fatih Karahan",
            "evidence_status": "partially_corroborated",
            "source": "Enflasyon Raporu",
        },
    ]
    tweets = format_x_thread(
        "TCMB Faiz Kararı", "Merkez Bankası faizi sabit bıraktı.", claims, event_id=42
    )

    assert len(tweets) == 3
    assert "📌 TCMB Faiz Kararı" in tweets[0]
    assert "event/42" in tweets[0]
    assert all(len(t) <= 280 for t in tweets)
    assert "[Teyitli]" in tweets[1]
    assert "[Kısmi Teyit]" in tweets[2]


def test_format_linkedin_post() -> None:
    """LinkedIn profesyonel makale formatlayıcı testi."""
    claims = [
        {
            "claim_text": "İhracat Ağustos ayında %4 arttı",
            "speaker": "Ticaret Bakanlığı",
            "evidence_status": "strongly_corroborated",
        }
    ]
    post = format_linkedin_post(
        "Ağustos Dış Ticaret Rakamları", "İhracat artış trendini sürdürüyor.", claims, event_id=55
    )

    assert "ANALİZ & POLİTİKA İSTİHBARATI" in post
    assert "Özet Değerlendirme:" in post
    assert "Doğrulandı" in post
    assert "#PolitikDesk" in post
    assert "event/55" in post


def test_format_telegram_note() -> None:
    """Telegram kompakt bülten notu testi."""
    claims = [
        {
            "claim_text": "Cari açık 18 milyar dolara geriledi",
            "evidence_status": "strongly_corroborated",
        }
    ]
    note = format_telegram_note(
        "Cari Denge Verisi", "Cari dengede iyileşme sürüyor.", claims, event_id=88
    )

    assert "⚡ *Cari Denge Verisi*" in note
    assert "🟢 Cari açık 18 milyar dolara geriledi" in note
    assert "event/88" in note


def test_format_newsletter_markdown() -> None:
    """Newsletter zengin markdown formatlayıcı testi."""
    claims = [
        {
            "claim_text": "Bütçe açığı azaldı",
            "speaker": "Hazine",
            "evidence_status": "strongly_corroborated",
        }
    ]
    md = format_newsletter_markdown(
        "Mali Disiplin Raporu", "Bütçe dengesi korundu.", claims, event_id=99
    )

    assert "# Mali Disiplin Raporu" in md
    assert "| # | İddia / Beyan | Konuşmacı | Kanıt Durumu |" in md
    assert "🟢 Teyitli" in md


def test_check_anti_repetition_guard() -> None:
    """Editoryal dejavu / tekrar koruması testi."""
    # 1. Benzer başlık varsa tespit etmeli
    fake_rows = [
        {
            "id": 12,
            "title": "Merkez Bankası Faiz Kararını Açıkladı",
            "created_at": "2026-08-10",
            "days_ago": 13,
        }
    ]
    with patch("politikdesk.editorial.omnichannel.connection") as mock_conn:
        mock_cur = MagicMock()
        mock_cur.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = fake_rows
        mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cur

        alert = check_anti_repetition("Merkez Bankası Faiz Kararı Açıklandı", "Detaylar...")
        assert isinstance(alert, RepetitionAlert)
        assert alert.is_duplicate_risk is True
        assert alert.matched_draft_id == 12

    # 2. Farklı içerikte temiz dönmeli
    with patch("politikdesk.editorial.omnichannel.connection") as mock_conn:
        mock_cur = MagicMock()
        mock_cur.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = []
        mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cur

        alert_clean = check_anti_repetition("TBMM Yeni Yargı Paketi Görüşmeleri", "Detaylar...")
        assert alert_clean.is_duplicate_risk is False


def test_build_omnichannel_package_from_event() -> None:
    """Olay üzerinden tam paket oluşturma testi."""
    fake_event_row = {
        "id": 77,
        "title": "Asgari Ücret Tespit Komisyonu Toplandı",
        "summary": "Komisyon ilk toplantısını yaptı.",
        "claims_json": [
            {
                "claim_text": "İlk toplantı tamamlandı",
                "speaker": "Bakan",
                "evidence_status": "strongly_corroborated",
            }
        ],
    }
    with patch("politikdesk.editorial.omnichannel.connection") as mock_conn:
        mock_cur = MagicMock()
        mock_cur.__enter__.return_value = mock_cur
        mock_cur.fetchone.return_value = fake_event_row
        mock_cur.fetchall.return_value = []
        mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cur

        pkg = build_omnichannel_package_from_event(77)
        assert isinstance(pkg, OmnichannelPackage)
        assert pkg.event_id == 77
        assert len(pkg.x_thread) >= 2
        assert "LinkedIn" not in pkg.linkedin_post or len(pkg.linkedin_post) > 50
        assert "telegram_note" in pkg.to_dict()


def test_api_events_omnichannel_endpoint() -> None:
    """GET /api/events/{id}/omnichannel JSON uç testi."""
    fake_pkg = OmnichannelPackage(
        event_id=10,
        draft_id=None,
        title="Test Başlık",
        lead="Test Özet",
        x_thread=["t1", "t2"],
        linkedin_post="li post",
        telegram_note="tg note",
        newsletter_markdown="news md",
        safety_gate={"passed": True},
        repetition_alert={"is_duplicate_risk": False},
    )
    with patch(
        "politikdesk.editorial.omnichannel.build_omnichannel_package_from_event",
        return_value=fake_pkg,
    ):
        resp = client.get("/api/events/10/omnichannel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_id"] == 10
        assert "x_thread" in data
        assert "linkedin_post" in data
        assert "telegram_note" in data
