"""S2 Accountability Case ve Political Memory Servis Entegrasyon Testleri (Spec v3.4 §8.3, §14.1)."""

from __future__ import annotations

from typing import Any

import pytest

from politikdesk.political_memory.accountability import (
    EvidenceChainNode,
    build_accountability_case,
)
from politikdesk.political_memory.relation_engine import (
    RelationResult,
    RelationScoreBreakdown,
)
from politikdesk.political_memory.service import (
    record_relation,
)


def test_build_accountability_case_data_integrity() -> None:
    p_node = EvidenceChainNode(
        step_number=1,
        step_type="promise",
        event_id=101,
        event_title="Mülakatın kaldırılması vaadi",
        source_name="Cumhurbaşkanlığı",
        source_url="https://cb.gov.tr/aciklama/1",
        published_at="2026-08-01T10:00:00Z",
        quote_or_claim="Kamuda mülakat kaldırılacak",
        claim_id=501,
        evidence_status="attribution_verified",
    )
    o_node = EvidenceChainNode(
        step_number=2,
        step_type="legislative_action",
        event_id=102,
        event_title="Kanun teklifi meclise sunuldu",
        source_name="TBMM",
        source_url="https://tbmm.gov.tr/kanun/1",
        published_at="2026-08-10T12:00:00Z",
        quote_or_claim="Teklif komisyona sunuldu",
        claim_id=502,
        evidence_status="strongly_corroborated",
    )

    breakdown = RelationScoreBreakdown(0.8, 1.0, 0.5, 0.9, 1.0, 0.35, 0.95)
    rel = RelationResult(
        source_event_id=101,
        target_event_id=102,
        relation_type="fulfils",
        confidence=0.95,
        status="verified",
        score_breakdown=breakdown,
        evidence_payload={"matched": True},
        explanation="Test explanation",
    )

    case = build_accountability_case(
        case_id="case-001",
        actor_name="Hükümet Sözcüsü",
        institution="Cumhurbaşkanlığı",
        topic="kamu_istihdami",
        promise_node=p_node,
        outcome_node=o_node,
        relation=rel,
    )

    d = case.to_dict()
    assert d["case_id"] == "case-001"
    assert d["actor_name"] == "Hükümet Sözcüsü"
    assert d["outcome_relation"] == "fulfils"
    assert d["confidence_level"] == "verified"
    assert len(d["evidence_chain"]) == 2
    assert "disclaimer" in d
    assert "şahsi cezai" in d["disclaimer"]


@pytest.mark.db
def test_record_relation_and_fetch_with_enhanced_fields(db_conn: Any) -> None:
    """Veritabanına confidence, evidence_payload ve status ile kayıt denetimi."""
    with db_conn.cursor() as cur:
        # 2 geçici olay oluştur
        cur.execute(
            """
            INSERT INTO events (title, first_reported_at, last_update_at, vertical)
            VALUES ('S2 Test Olayı 1', now(), now(), 'legislation')
            RETURNING id;
            """
        )
        e1 = cur.fetchone()["id"]

        cur.execute(
            """
            INSERT INTO events (title, first_reported_at, last_update_at, vertical)
            VALUES ('S2 Test Olayı 2', now(), now(), 'legislation')
            RETURNING id;
            """
        )
        e2 = cur.fetchone()["id"]
        db_conn.commit()

    try:
        payload = {"matched_topics": ["kamu"], "score": 0.88}
        record_relation(
            from_event_id=e1,
            to_event_id=e2,
            relation="fulfils",
            similarity=0.92,
            created_by="system",
            confidence=0.88,
            evidence_payload=payload,
            status="supported",
        )

        with db_conn.cursor() as cur:
            cur.execute(
                """
                SELECT relation, similarity, confidence, status, evidence_payload
                FROM event_relations
                WHERE from_event_id = %s AND to_event_id = %s;
                """,
                (e1, e2),
            )
            row = cur.fetchone()
            assert row is not None
            assert row["relation"] == "fulfils"
            assert round(row["confidence"], 2) == 0.88
            assert row["status"] == "supported"
            assert row["evidence_payload"]["matched_topics"] == ["kamu"]

    finally:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM event_relations WHERE from_event_id = %s;", (e1,))
            cur.execute("DELETE FROM events WHERE id IN (%s, %s);", (e1, e2))
            db_conn.commit()


def test_sparkline_svg_rendering() -> None:
    """Satır içi mini sparkline SVG grafiği doğrulaması."""
    from politikdesk.web.ui.charts import sparkline

    # Boş veya tek noktalı veri için boş string dönmeli
    assert sparkline([]) == ""
    assert sparkline([42.0]) == ""

    # Normal seri için geçerli SVG dönmeli
    svg = sparkline([10.0, 15.0, 8.0, 22.0, 30.0], width=80, height=24)
    assert "<svg" in svg
    assert "</svg>" in svg
    assert 'class="sparkline"' in svg
    assert 'width="80"' in svg
    assert 'height="24"' in svg
    assert "<polyline" in svg
    assert "<circle" in svg


def test_political_memory_models_module_import() -> None:
    """Modülerleştirilmiş models.py dosyası doğrudan import edilebilir ve tipleri tamdır."""
    from datetime import UTC, datetime

    from politikdesk.political_memory.models import (
        EventData,
        RelationResult,
        RelationScoreBreakdown,
    )

    ev = EventData(
        event_id=1,
        title="Test Başlık",
        published_at=datetime.now(UTC),
        entities=frozenset(["TCMB"]),
    )
    assert ev.event_id == 1
    assert "TCMB" in ev.entities

    breakdown = RelationScoreBreakdown(1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 1.0)
    assert breakdown.to_dict()["total_score"] == 1.0

    res = RelationResult(
        source_event_id=1,
        target_event_id=2,
        relation_type="fulfils",
        confidence=0.90,
        status="verified",
        score_breakdown=breakdown,
        evidence_payload={},
        explanation="Doğrulandı",
    )
    assert res.is_valid is True

