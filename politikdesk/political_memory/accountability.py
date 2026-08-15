"""Hesap Sor (Accountability Engine) Kanıt Kütüğü ve Vaka Modelleri (S2 · Spec v3.4 §14.1).

Bu modül, siyasi vaatler, hükümet kararları, TBMM kanun teklifleri ve
Sayıştay denetim raporları arasında kanıta dayalı hesap verebilirlik vakaları (AccountabilityCase)
ve denetlenebilir kanıt zincirleri (EvidenceChain) oluşturur.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from politikdesk.political_memory.relation_engine import RelationResult

LEGAL_DISCLAIMER = (
    "Bu analiz resmî ve doğrulanmış veri kaynaklarının deterministik eşleştirmesine dayanır. "
    "Doğrudan şahsi cezai veya hukuki sorumluluk hükmü içermez; editoryal kanıt zinciridir."
)


@dataclass(frozen=True)
class EvidenceChainNode:
    step_number: int
    step_type: str  # "promise", "policy_decision", "legislative_action", "audit_finding"
    event_id: int
    event_title: str
    source_name: str
    source_url: str
    published_at: str
    quote_or_claim: str
    claim_id: int | None = None
    evidence_status: str = "unverified"


@dataclass
class AccountabilityCase:
    case_id: str
    actor_name: str
    institution: str
    topic: str
    promise_event_id: int
    promise_claim_id: int
    promise_text: str
    promise_date: str
    outcome_relation: str  # "fulfils", "fails", "contradicts", "updates", "pending"
    confidence_level: str  # "verified", "supported", "inferred", "unresolved"
    evidence_chain: list[EvidenceChainNode] = field(default_factory=list)
    relation_details: dict[str, Any] = field(default_factory=dict)
    disclaimer: str = (
        "Bu analiz resmî ve doğrulanmış veri kaynaklarının deterministik eşleştirmesine dayanır. "
        "Doğrudan şahsi cezai veya hukuki sorumluluk hükmü içermez; editoryal kanıt zinciridir."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "actor_name": self.actor_name,
            "institution": self.institution,
            "topic": self.topic,
            "promise_event_id": self.promise_event_id,
            "promise_claim_id": self.promise_claim_id,
            "promise_text": self.promise_text,
            "promise_date": self.promise_date,
            "outcome_relation": self.outcome_relation,
            "confidence_level": self.confidence_level,
            "evidence_chain": [asdict(node) for node in self.evidence_chain],
            "relation_details": self.relation_details,
            "disclaimer": self.disclaimer,
        }


def build_accountability_case(
    *,
    case_id: str,
    actor_name: str,
    institution: str,
    topic: str,
    promise_node: EvidenceChainNode,
    outcome_node: EvidenceChainNode | None = None,
    relation: RelationResult | None = None,
) -> AccountabilityCase:
    """Tekil bir vaat ve sonraki icraat/denetim adımlarından vaka oluşturur."""
    chain = [promise_node]
    if outcome_node:
        chain.append(outcome_node)

    outcome_rel = relation.relation_type if relation else "pending"
    confidence = relation.status if relation else "unresolved"

    return AccountabilityCase(
        case_id=case_id,
        actor_name=actor_name,
        institution=institution,
        topic=topic,
        promise_event_id=promise_node.event_id,
        promise_claim_id=promise_node.claim_id or 0,
        promise_text=promise_node.quote_or_claim,
        promise_date=promise_node.published_at,
        outcome_relation=outcome_rel,
        confidence_level=confidence,
        evidence_chain=chain,
        relation_details=relation.evidence_payload if relation else {},
    )
