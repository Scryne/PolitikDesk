"""Türkçe Siyaset ve Yasama Dikeyi Reranker Modülü (Spec v3.5 §11.4).

Bu modül, standart vektör benzerliği (ANN Cosine) ile dönen aday olayları,
Türkçe siyasi aktör/kurum ontolojisi, anayasal akış ve terim örtüşmesiyle yeniden
sıralar (rerank).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from politikdesk.nlp.entities import jaccard


@dataclass(frozen=True)
class RerankedCandidate:
    event_id: int
    base_similarity: float
    rerank_score: float
    actor_overlap: float
    topic_match: bool
    explanation: str


class TurkishPoliticalReranker:
    """Türkçe siyaset ve yasama odaklı aday yeniden sıralayıcısı."""

    def __init__(
        self,
        base_weight: float = 0.50,
        entity_weight: float = 0.30,
        topic_weight: float = 0.20,
    ) -> None:
        self.base_weight = base_weight
        self.entity_weight = entity_weight
        self.topic_weight = topic_weight

    def rerank(
        self,
        article_text: str,
        article_entities: frozenset[str],
        article_topics: tuple[str, ...],
        candidates: list[dict[str, Any]],
    ) -> list[RerankedCandidate]:
        """Aday olayları zenginleştirilmiş metriklerle yeniden sıralar."""
        from politikdesk.feature_flags import is_reranker_enabled

        if not is_reranker_enabled():
            # Devre dışı ise saf vektör benzerliğine göre sıralı döndür
            return [
                RerankedCandidate(
                    event_id=c["event_id"],
                    base_similarity=float(c.get("similarity", 0.0)),
                    rerank_score=float(c.get("similarity", 0.0)),
                    actor_overlap=0.0,
                    topic_match=False,
                    explanation="reranker_disabled_fallback_to_base_similarity",
                )
                for c in sorted(
                    candidates,
                    key=lambda x: float(x.get("similarity", 0.0)),
                    reverse=True,
                )
            ]

        reranked: list[RerankedCandidate] = []

        for cand in candidates:
            event_id = cand["event_id"]
            base_sim = float(cand.get("similarity", 0.0))
            cand_entities = frozenset(cand.get("entities", []))
            cand_topics = set(cand.get("topics", []))

            # 1. Varlık örtüşmesi (Jaccard)
            overlap = (
                jaccard(article_entities, cand_entities)
                if (article_entities and cand_entities)
                else 0.0
            )

            # 2. Konu / Dikey örtüşmesi
            topic_match = (
                bool(set(article_topics) & cand_topics)
                if (article_topics and cand_topics)
                else False
            )
            topic_score = 1.0 if topic_match else 0.0

            # 3. Bileşik Puan
            final_score = (
                (self.base_weight * base_sim)
                + (self.entity_weight * overlap)
                + (self.topic_weight * topic_score)
            )

            reranked.append(
                RerankedCandidate(
                    event_id=event_id,
                    base_similarity=base_sim,
                    rerank_score=round(final_score, 4),
                    actor_overlap=round(overlap, 4),
                    topic_match=topic_match,
                    explanation=(
                        f"base={base_sim:.2f} + ent_jaccard={overlap:.2f} + topic={topic_match}"
                    ),
                )
            )

        # Rerank puanına göre azalan sırala
        return sorted(reranked, key=lambda r: r.rerank_score, reverse=True)
