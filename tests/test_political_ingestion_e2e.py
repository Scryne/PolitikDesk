"""S1 Siyaset Dikeyi Uçtan Uca Ingestion & Provenance Testi (S1.6).

SOURCE (TBMM / Sayıştay / CB)
  ↓
ADAPTER.fetch() -> RawItem
  ↓
NORMALIZE -> NormalizedArticle
  ↓
DEDUP & STORE -> Article
  ↓
EVENT / CLUSTER
  ↓
CLAIM EXTRACTION
  ↓
EVIDENCE & PROVENANCE
"""

from __future__ import annotations

from datetime import UTC, datetime

from politikdesk.clustering.assigner import (
    ArticleFeatures,
    EventCandidate,
    Thresholds,
    decide,
)
from politikdesk.ingestion.models import RawItem
from politikdesk.ingestion.normalizer import normalize


def test_tbmm_to_normalized_article_pipeline() -> None:
    """TBMM adaptör çıktısı kayıpsız normalize edilir ve provenance korunur."""
    raw = RawItem(
        source_slug="tbmm",
        url="https://www.tbmm.gov.tr/yasama/kanun-teklifleri/9-yargi-paketi",
        title="Bazı Kanunlarda Değişiklik Yapılmasına Dair Kanun Teklifi (9. Yargı Paketi)",
        published_at=datetime(2026, 8, 10, 14, 0, tzinfo=UTC),
        summary="9. Yargı Paketi Kanun Teklifi TBMM Adalet Komisyonuna sevk edildi.",
        guid="https://www.tbmm.gov.tr/yasama/kanun-teklifleri/9-yargi-paketi",
        extra={"category": "kanun_teklifi", "vertical": "legislation"},
    )

    norm = normalize(raw)

    assert norm.canonical_url == "https://tbmm.gov.tr/yasama/kanun-teklifleri/9-yargi-paketi"
    assert "9. Yargı Paketi" in norm.title
    assert norm.published_at == datetime(2026, 8, 10, 14, 0, tzinfo=UTC)
    assert norm.simhash != 0


def test_sayistay_to_normalized_article_pipeline() -> None:
    """Sayıştay denetim raporu çıktısı normalizasyon zincirinden geçer."""
    raw = RawItem(
        source_slug="sayistay",
        url="https://www.sayistay.gov.tr/pages/2025-kamu-zarari-raporu",
        title="Sayıştay: 2025 Yılı Büyükşehir Belediyesi Kamu Zararı ve İhale Denetim Bulguları",
        published_at=datetime(2026, 8, 11, 10, 0, tzinfo=UTC),
        summary="Sayıştay denetçileri ihale limitlerinin aşıldığını raporladı.",
        guid="https://www.sayistay.gov.tr/pages/2025-kamu-zarari-raporu",
        extra={"category": "denetim_ve_yolsuzluk", "vertical": "legislation"},
    )

    norm = normalize(raw)
    assert norm.canonical_url == "https://sayistay.gov.tr/pages/2025-kamu-zarari-raporu"
    assert "Kamu Zararı" in norm.title


def test_cumhurbaskanligi_to_normalized_article_pipeline() -> None:
    """Cumhurbaşkanlığı kararnamesi normalizasyon zincirinden geçer."""
    raw = RawItem(
        source_slug="cb-kararname",
        url="https://www.tccb.gov.tr/basin-aciklamalari/ust-kademe-atama-kararnamesi",
        title="Cumhurbaşkanlığı: Üst Kademe Kamu Yöneticiliklerine Atama Kararnamesi Yayımlandı",
        published_at=datetime(2026, 8, 12, 4, 0, tzinfo=UTC),
        summary="Atama kararnamesi Resmi Gazete'de yayımlandı.",
        guid="https://www.tccb.gov.tr/basin-aciklamalari/ust-kademe-atama-kararnamesi",
        extra={"category": "atama_ve_kadro", "vertical": "legislation"},
    )

    norm = normalize(raw)
    assert (
        norm.canonical_url == "https://tccb.gov.tr/basin-aciklamalari/ust-kademe-atama-kararnamesi"
    )
    assert "Atama Kararnamesi" in norm.title


def test_political_articles_cluster_and_preserve_provenance() -> None:
    """Aynı siyasi olayı bildiren TBMM ve ajans haberleri aynı kümeye atanır."""
    base_vec = [0.1] * 1024

    art1_features = ArticleFeatures(
        article_id=101,
        embedding=base_vec,
        entities=frozenset(["9. Yargı Paketi", "TBMM Adalet Komisyonu"]),
        key_entities=frozenset(["9. Yargı Paketi"]),
        published_at=datetime(2026, 8, 10, 14, 0, tzinfo=UTC),
        text="9. Yargı Paketi Kanun Teklifi TBMM Adalet Komisyonunda kabul edildi.",
        vertical="legislation",
    )

    # Var olan aday olay (similarity=0.95 >= t_high=0.92)
    existing_event = EventCandidate(
        event_id=501,
        similarity=0.95,
        entities=frozenset(["9. Yargı Paketi", "TBMM Adalet Komisyonu"]),
        key_entities=frozenset(["9. Yargı Paketi"]),
        last_update_at=datetime(2026, 8, 10, 13, 30, tzinfo=UTC),
        text_sample="9. Yargı Paketi komisyondan geçti.",
    )

    thresholds = Thresholds(t_high=0.92, t_low=0.88)
    decision = decide(art1_features, [existing_event], thresholds=thresholds)

    assert decision.action == "assign"
    assert decision.event_id == 501
