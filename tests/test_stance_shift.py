from __future__ import annotations

from politikdesk.political_memory.service import ActorMemory, MemoryEntry
from politikdesk.political_memory.stance_shift import detect_stance_shifts_from_memory


def test_detect_shift_from_relation_chain():
    mem = ActorMemory(
        actor_name="Mehmet Şimşek",
        total_claims=2,
        promises=[
            MemoryEntry(
                event_id=1,
                event_title="Enflasyon Hedefi Açıklaması",
                claim_id=10,
                claim_text="Yıl sonu enflasyon %20 olacak",
                claim_type="promise",
                evidence_status="strongly_corroborated",
                first_reported_at="2026-01-10T10:00:00Z",
            )
        ],
        attributions=[],
        facts_and_numbers=[],
        relation_chains=[
            {
                "from_event_id": 1,
                "to_event_id": 2,
                "from_title": "Enflasyon Hedefi Açıklaması",
                "to_title": "TÜİK Yıl Sonu Enflasyonu %45 Açıkladı",
                "relation": "fails",
                "confidence": 0.95,
                "evidence_payload": {"topic": "Enflasyon", "source_claim": "Hedef %20", "target_claim": "Gerçekleşen %45"},
            }
        ],
    )

    shifts = detect_stance_shifts_from_memory(mem)
    assert len(shifts) == 1
    s = shifts[0]
    assert s.actor_name == "Mehmet Şimşek"
    assert s.shift_type == "broken_promise"
    assert s.earlier_event_id == 1
    assert s.later_event_id == 2
    assert s.confidence == 0.95
    assert "Enflasyon" in s.topic_or_metric


def test_detect_reversal_from_polar_keywords():
    mem = ActorMemory(
        actor_name="Ahmet Yılmaz",
        total_claims=2,
        promises=[],
        attributions=[
            MemoryEntry(
                event_id=10,
                event_title="Faiz Politikası Açıklaması 2025",
                claim_id=101,
                claim_text="Faiz oranları derhal indirilmeli ve parasal gevşeme başlamalı",
                claim_type="attribution",
                evidence_status="strongly_corroborated",
                first_reported_at="2025-06-01T10:00:00Z",
            ),
            MemoryEntry(
                event_id=11,
                event_title="Faiz Politikası Açıklaması 2026",
                claim_id=102,
                claim_text="Enflasyonla mücadele için faiz artırılmalı ve parasal sıkılaşma sürmeli",
                claim_type="attribution",
                evidence_status="strongly_corroborated",
                first_reported_at="2026-02-01T10:00:00Z",
            ),
        ],
        facts_and_numbers=[],
        relation_chains=[],
    )

    shifts = detect_stance_shifts_from_memory(mem)
    assert len(shifts) == 1
    s = shifts[0]
    assert s.actor_name == "Ahmet Yılmaz"
    assert s.shift_type == "reversal"
    assert s.earlier_event_id == 10
    assert s.later_event_id == 11
    assert s.time_span_days > 200


def test_detect_numeric_divergence():
    mem = ActorMemory(
        actor_name="Cevdet Yılmaz",
        total_claims=2,
        promises=[
            MemoryEntry(
                event_id=20,
                event_title="Büyüme Hedefi OVP",
                claim_id=201,
                claim_text="2026 yılı büyüme hedefimiz %40 seviyesindedir",
                claim_type="promise",
                evidence_status="strongly_corroborated",
                first_reported_at="2026-01-01T10:00:00Z",
            ),
            MemoryEntry(
                event_id=21,
                event_title="Büyüme Revizyonu",
                claim_id=202,
                claim_text="Büyüme tahminimiz %15 olarak revize edilmiştir",
                claim_type="promise",
                evidence_status="strongly_corroborated",
                first_reported_at="2026-07-01T10:00:00Z",
            ),
        ],
        attributions=[],
        facts_and_numbers=[],
        relation_chains=[],
    )

    shifts = detect_stance_shifts_from_memory(mem)
    assert len(shifts) == 1
    s = shifts[0]
    assert s.shift_type == "numeric_divergence"
    assert s.earlier_event_id == 20
    assert s.later_event_id == 21
    d = s.to_dict()
    assert d["shift_type"] == "numeric_divergence"
    assert "Sayısal Gösterge" in d["topic_or_metric"]
