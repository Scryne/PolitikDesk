"""S2 Relation Engine Birim Testleri (Spec v3.4 §7.3, §8.3, §14.1)."""

from __future__ import annotations

from datetime import datetime

from politikdesk.political_memory.relation_engine import (
    EventData,
    RelationScoreBreakdown,
    evaluate_relation,
)


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def test_relation_score_breakdown_dict() -> None:
    b = RelationScoreBreakdown(
        entity_score=0.8,
        institution_score=1.0,
        topic_score=0.5,
        semantic_score=0.9,
        temporal_score=1.0,
        explicit_boost=0.35,
        total_score=0.95,
    )
    d = b.to_dict()
    assert d["entity_score"] == 0.8
    assert d["institution_score"] == 1.0
    assert d["explicit_boost"] == 0.35
    assert d["total_score"] == 0.95


def test_explicit_law_number_match_boosts_confidence() -> None:
    src = EventData(
        event_id=1,
        title="TBMM'ye 7440 Sayılı Kanun Teklifi Sunuldu",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        institution="TBMM",
        claims=({"claim_text": "7440 sayılı kanun teklifi sunuldu", "claim_type": "fact"},),
    )
    tgt = EventData(
        event_id=2,
        title="7440 Sayılı Kanun TBMM Genel Kurulunda Kabul Edildi",
        published_at=_dt("2026-08-10T15:00:00+03:00"),
        institution="TBMM",
        claims=({"claim_text": "7440 sayılı kanun kabul edildi", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt, semantic_similarity=0.95)
    assert res.is_valid
    assert res.status == "verified"
    assert res.relation_type == "fulfils"
    assert res.score_breakdown.explicit_boost >= 0.35


def test_sayistay_audit_finding_fails_unkept_promise() -> None:
    src = EventData(
        event_id=10,
        title="Belediye Başkanı: İhalelerde doğrudan temin sınırlandırılacak",
        published_at=_dt("2026-07-01T10:00:00+03:00"),
        actor="Belediye Başkanı",
        institution="Kadıköy Belediyesi",
        topics=("belediye_yonetimi", "ihale_ve_kamu"),
        claims=({"claim_text": "Doğrudan temin sınırlandırılacak", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=11,
        title="Sayıştay Raporu: Kadıköy Belediyesinde doğrudan temin limiti mevzuata aykırı aşıldı",
        published_at=_dt("2026-08-10T10:00:00+03:00"),
        actor="Sayıştay",
        institution="Kadıköy Belediyesi",
        topics=("belediye_yonetimi", "denetim_ve_yolsuzluk"),
        claims=({"claim_text": "Doğrudan temin limiti aşıldı", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt, semantic_similarity=0.88)
    assert res.is_valid
    assert res.relation_type == "fails"
    assert res.status in ("supported", "verified")


def test_temporal_inversion_fails_closed() -> None:
    """Gelecekteki vaat geçmişteki Sayıştay bulgusunu doğrulayamaz."""
    src = EventData(
        event_id=20,
        title="2027 Yılında Sağlık Personeli Atamaları Artırılacak",
        published_at=_dt("2026-08-14T10:00:00+03:00"),
        actor="Sağlık Bakanı",
        institution="Sağlık Bakanlığı",
        claims=({"claim_text": "2027 atamaları artırılacak", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=21,
        title="Sayıştay Raporu: Sağlık Bakanlığı 2025 yılı bütçe açığı tespiti",
        published_at=_dt("2026-08-01T09:00:00+03:00"),
        institution="Sağlık Bakanlığı",
        claims=({"claim_text": "2025 bütçe açığı tespit edildi", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt, semantic_similarity=0.75)
    assert not res.is_valid
    assert res.status == "unresolved"
    assert "temporal_inversion" in res.evidence_payload.get("reason", "")


def test_institution_mismatch_fails_closed() -> None:
    src = EventData(
        event_id=30,
        title="İlçe Belediyesi Park İhaleleri Şeffaf Olacak",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        institution="Beşiktaş Belediyesi",
        topics=("belediye_yonetimi",),
        claims=({"claim_text": "İhaleler açık yapılacak", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=31,
        title="Sayıştay Raporu: Tarım Bakanlığında taşıt kiralama mevzuatına aykırılık",
        published_at=_dt("2026-08-10T10:00:00+03:00"),
        institution="Tarım ve Orman Bakanlığı",
        topics=("denetim_ve_yolsuzluk",),
        claims=({"claim_text": "Taşıt kiralama mevzuata aykırı", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt, semantic_similarity=0.40)
    assert not res.is_valid
    assert res.status == "unresolved"
    assert res.evidence_payload.get("reason") == "institution_mismatch"
