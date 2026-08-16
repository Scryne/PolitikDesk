"""Siyasi Hafıza ve İlişki Motoru Veri Modelleri (Spec v3.4 §7.3, §8.3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

RelationType = Literal["same_thread", "precedes", "updates", "contradicts", "fulfils", "fails"]
RelationStatus = Literal["inferred", "supported", "verified", "unresolved"]


@dataclass(frozen=True)
class EventData:
    event_id: int
    title: str
    published_at: datetime
    entities: frozenset[str] = frozenset()
    key_entities: frozenset[str] = frozenset()
    institution: str | None = None
    actor: str | None = None
    topics: tuple[str, ...] = ()
    claims: tuple[dict[str, Any], ...] = ()
    embedding: list[float] | None = None
    vertical: str = "legislation"


@dataclass(frozen=True)
class RelationScoreBreakdown:
    entity_score: float
    institution_score: float
    topic_score: float
    semantic_score: float
    temporal_score: float
    explicit_boost: float
    total_score: float

    def to_dict(self) -> dict[str, float]:
        return {
            "entity_score": round(self.entity_score, 3),
            "institution_score": round(self.institution_score, 3),
            "topic_score": round(self.topic_score, 3),
            "semantic_score": round(self.semantic_score, 3),
            "temporal_score": round(self.temporal_score, 3),
            "explicit_boost": round(self.explicit_boost, 3),
            "total_score": round(self.total_score, 3),
        }


@dataclass(frozen=True)
class RelationResult:
    source_event_id: int
    target_event_id: int
    relation_type: RelationType
    confidence: float
    status: RelationStatus
    score_breakdown: RelationScoreBreakdown
    evidence_payload: dict[str, Any]
    explanation: str

    @property
    def is_valid(self) -> bool:
        return self.status != "unresolved" and self.confidence >= 0.60
