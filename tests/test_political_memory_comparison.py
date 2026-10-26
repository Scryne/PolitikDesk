"""Siyasi Hafıza Zamansal Söylem Karşılaştırma Modülü Testleri."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.political_memory.comparison import (
    _parse_year,
    compare_actor_statements,
    detect_polarity,
    get_known_comparison_topics,
    get_tracked_actors,
)
from politikdesk.political_memory.service import ActorMemory, MemoryEntry

client = TestClient(app)


def test_detect_polarity_helpers() -> None:
    """Söylem polaritesi tespit fonksiyonu testleri."""
    assert detect_polarity("Asgari ücreti kesinlikle artıracağız", "factual") == "support"
    assert detect_polarity("Bu faiz politikasına karşıyız, kabul edilemez", "factual") == "oppose"
    assert (
        detect_polarity("Bütçe görüşmeleri yarın saat 14:00'te başlayacak", "factual") == "neutral"
    )
    assert detect_polarity("Enflasyonu tek haneye düşüreceğiz", "promise") == "promise"


@pytest.mark.parametrize(
    ("input_str", "expected_year"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("unknown", None),
        ("invalid", None),
        ("2026", 2026),
        ("2025-01-15", 2025),
        ("2025/01/15", 2025),
        ("15.01.2025", 2025),
        ("2025-01-15T12:30:00", 2025),
        ("2025-01-15T12:30:00Z", 2025),
        ("0", None),
        ("0000", None),
        ("-1", None),
        ("20250", None),
        ("1999-12-31", 1999),
        ("15 Ocak 2024", 2024),
        ("2150", None),
        ("1850", None),
    ],
)
def test_parse_year_exhaustive_matrix(input_str: str | None, expected_year: int | None) -> None:
    """_parse_year fonksiyonunun kapsamlı girdi matrisi ve sınır durum testleri."""
    assert _parse_year(input_str) == expected_year


def test_undated_statement_invariant_protection() -> None:
    """Invariant Koruması: Tarihi belirsiz beyanlar hiçbir zaman 2026'ya yuvarlanmaz

    ve yapay söylem çelişkisi (false positive shift) üretmez.
    """
    fake_memories = [
        MemoryEntry(
            event_id=101,
            event_title="2018 Faiz İtirazı",
            claim_id=1,
            claim_text="Yüksek faiz politikasını kesinlikle reddediyoruz ve karşıyız",
            claim_type="factual",
            evidence_status="strongly_corroborated",
            first_reported_at="2018-05-10T10:00:00Z",
            speaker="Mehmet Şimşek",
            topic_tags=("faiz", "ekonomi"),
        ),
        MemoryEntry(
            event_id=102,
            event_title="Tarihi Belirsiz Destek Açıklaması",
            claim_id=2,
            claim_text="Ortodoks para politikası ve faiz artışını destekliyoruz",
            claim_type="factual",
            evidence_status="strongly_corroborated",
            first_reported_at="",  # Bilinmeyen / eksik tarih
            speaker="Mehmet Şimşek",
            topic_tags=("faiz", "para_politikasi"),
        ),
        MemoryEntry(
            event_id=103,
            event_title="2024 Faiz İtirazı",
            claim_id=3,
            claim_text="Aşırı faiz artışlarına karşıyız ve durdurulmalıdır",
            claim_type="factual",
            evidence_status="strongly_corroborated",
            first_reported_at="2024-03-20T12:00:00Z",
            speaker="Mehmet Şimşek",
            topic_tags=("faiz", "ekonomi"),
        ),
    ]

    fake_actor_mem = ActorMemory(
        actor_name="Mehmet Şimşek",
        total_claims=3,
        promises=[],
        attributions=[],
        facts_and_numbers=fake_memories,
    )

    with patch(
        "politikdesk.political_memory.comparison.get_actor_memory", return_value=fake_actor_mem
    ):
        res = compare_actor_statements("Mehmet Şimşek", topic="faiz", split_year=2020)

        # 1. Tarihsiz kayıt undated_statements listesine ayrılmış olmalı
        assert len(res.earlier_statements) == 1
        assert res.earlier_statements[0].year == 2018
        assert res.earlier_statements[0].stance_polarity == "oppose"

        assert len(res.later_statements) == 1
        assert res.later_statements[0].year == 2024
        assert res.later_statements[0].stance_polarity == "oppose"

        assert len(res.undated_statements) == 1
        assert res.undated_statements[0].year is None
        assert res.undated_statements[0].date_str == "Bilinmiyor"
        assert res.undated_statements[0].stance_polarity == "support"

        # 2. Tarihsiz kayıt 2026 sanılıp çelişki üretilmemeli (2018 oppose vs 2024 oppose -> tutarlı)
        assert res.shift_detected is False
        assert res.consistency_score >= 0.75
        assert "tutarlı" in res.shift_summary.casefold()


def test_compare_actor_statements_empty_actor() -> None:
    """Boş aktör adı sorgulandığında veritabanı yorulmadan temiz boş sonuç dönmeli."""
    res_empty = compare_actor_statements("")
    assert res_empty.actor_name == ""
    assert len(res_empty.earlier_statements) == 0
    assert len(res_empty.later_statements) == 0
    assert len(res_empty.undated_statements) == 0
    assert res_empty.shift_summary == "Aktör adı belirtilmedi."

    res_ws = compare_actor_statements("   ")
    assert res_ws.actor_name == ""
    assert res_ws.shift_summary == "Aktör adı belirtilmedi."


def test_get_known_comparison_topics_and_actors() -> None:
    """Popüler konu ve aktör listeleme testleri."""
    topics = get_known_comparison_topics()
    assert len(topics) >= 5
    assert any(t["slug"] == "faiz" for t in topics)
    assert any(t["slug"] == "enflasyon" for t in topics)

    actors = get_tracked_actors()
    assert isinstance(actors, list)
    assert len(actors) > 0


def test_true_semantic_parity_html_vs_json_api() -> None:
    """HTML (/memory/compare) ve JSON API (/api/memory/compare) domain semantik eşitlik testi.

    Aynı veri kümesi ve parametreler üzerinde iki arayüzün de aynı aktör,
    aynı beyan sayıları, aynı polariteler ve aynı tutarlılık skorunu yansıttığını doğrular.
    """
    fake_memories = [
        MemoryEntry(
            event_id=101,
            event_title="2023 Faiz Kararı Öncesi Açıklama",
            claim_id=1,
            claim_text="Yüksek faiz politikasını kesinlikle reddediyoruz",
            claim_type="factual",
            evidence_status="strongly_corroborated",
            first_reported_at="2023-04-10T10:00:00Z",
            speaker="Özgür Özel",
            topic_tags=("faiz", "ekonomi"),
        ),
        MemoryEntry(
            event_id=202,
            event_title="2025 Sıkılaşma Değerlendirmesi",
            claim_id=2,
            claim_text="Enflasyonla mücadelede faiz adımlarını destekliyoruz",
            claim_type="factual",
            evidence_status="strongly_corroborated",
            first_reported_at="2025-06-15T12:00:00Z",
            speaker="Özgür Özel",
            topic_tags=("faiz", "para_politikasi"),
        ),
        MemoryEntry(
            event_id=303,
            event_title="Belirsiz Tarihli Vaat",
            claim_id=3,
            claim_text="Asgari ücreti kesinlikle artıracağız",
            claim_type="promise",
            evidence_status="strongly_corroborated",
            first_reported_at=None,
            speaker="Özgür Özel",
            topic_tags=("faiz", "maas"),
        ),
    ]

    fake_actor_mem = ActorMemory(
        actor_name="Özgür Özel",
        total_claims=3,
        promises=[],
        attributions=[],
        facts_and_numbers=fake_memories,
    )

    with patch(
        "politikdesk.political_memory.comparison.get_actor_memory", return_value=fake_actor_mem
    ):
        # 1. JSON API Çağrısı
        api_resp = client.get(
            "/api/memory/compare",
            params={"actor": "Özgür Özel", "topic": "faiz", "year": 2025, "limit": 50},
        )
        assert api_resp.status_code == 200
        json_data = api_resp.json()

        # 2. HTML Sayfa Çağrısı
        html_resp = client.get(
            "/memory/compare",
            params={"actor": "Özgür Özel", "topic": "faiz", "year": 2025, "limit": 50},
        )
        assert html_resp.status_code == 200
        html_text = html_resp.text

        # 3. Domain Semantik Eşitlik Doğrulaması
        assert json_data["actor_name"] == "Özgür Özel"
        assert "Özgür Özel" in html_text

        # Earlier statements
        assert len(json_data["earlier_statements"]) == 1
        earlier_stmt = json_data["earlier_statements"][0]
        assert earlier_stmt["year"] == 2023
        assert earlier_stmt["stance_polarity"] == "oppose"
        assert earlier_stmt["claim_text"] in html_text
        assert "2023-04-10" in html_text

        # Later statements
        assert len(json_data["later_statements"]) == 1
        later_stmt = json_data["later_statements"][0]
        assert later_stmt["year"] == 2025
        assert later_stmt["stance_polarity"] == "support"
        assert later_stmt["claim_text"] in html_text
        assert "2025-06-15" in html_text

        # Undated statements
        assert len(json_data["undated_statements"]) == 1
        undated_stmt = json_data["undated_statements"][0]
        assert undated_stmt["year"] is None
        assert undated_stmt["date_str"] == "Bilinmiyor"
        assert "Tarihi Belirsiz Beyanlar" in html_text
        assert undated_stmt["claim_text"] in html_text

        # Söylem Kayması ve Tutarlılık Skoru
        assert json_data["shift_detected"] is True
        assert json_data["consistency_score"] == 0.35
        assert "%35" in html_text  # KPI'da Tutarlılık Skoru %35 görünmeli
        assert "Ayrışma" in html_text or "Savunma" in html_text


@pytest.mark.db
def test_api_turkish_characters_and_encoding() -> None:
    """Türkçe karakter içeren sorgularda (Mehmet Şimşek, Özgür Özel) UTF-8 güvenliği."""
    for actor in ("Mehmet Şimşek", "Özgür Özel", "Fatih Karahan"):
        resp = client.get("/api/memory/compare", params={"actor": actor, "limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert data["actor_name"] == actor
        assert "earlier_statements" in data
        assert "later_statements" in data
        assert "undated_statements" in data
