"""Türkçe Siyaset Reranker ve Kümeleme Hassasiyet Karşılaştırma Testleri."""

from __future__ import annotations

from politikdesk.clustering.reranker import TurkishPoliticalReranker


def test_reranker_prioritizes_entity_and_topic_match() -> None:
    """Reranker, benzer embedding'e sahip ama farklı aktörleri içeren olaylar arasından doğru olanı öne almalı."""
    reranker = TurkishPoliticalReranker(base_weight=0.50, entity_weight=0.30, topic_weight=0.20)

    article_text = "TBMM Adalet Komisyonunda 9. Yargı Paketi maddeleri görüşüldü."
    article_entities = frozenset(["TBMM Adalet Komisyonu", "9. Yargı Paketi", "Yılmaz Tunç"])
    article_topics = ("kanun_teklifleri", "yargi")

    candidates = [
        {
            # Genel ekonomi haberi (yüksek base similarity ama sıfır varlık örtüşmesi)
            "event_id": 101,
            "similarity": 0.88,
            "entities": ["TCMB", "Mehmet Şimşek", "enflasyon"],
            "topics": ["enflasyon"],
        },
        {
            # Gerçek ilgili siyasi olay (biraz daha düşük base similarity ama tam varlık ve konu eşleşmesi)
            "event_id": 202,
            "similarity": 0.85,
            "entities": ["TBMM Adalet Komisyonu", "9. Yargı Paketi", "Yılmaz Tunç"],
            "topics": ["kanun_teklifleri", "yargi"],
        },
    ]

    results = reranker.rerank(
        article_text,
        article_entities,
        article_topics,
        candidates,
    )

    # 202 numaralı olay rerank sonrası 1. sıraya yükselmeli
    assert results[0].event_id == 202
    assert results[0].rerank_score > results[1].rerank_score
    assert results[0].actor_overlap == 1.0
    assert results[0].topic_match is True
