"""İlişki Orkestrasyonu ve Idempotent Kayıt Katmanı (S3 · Spec v3.4 §14.1).

Bu modül, aday filtreleme (candidate_filter) ile deterministik ilişki motorunu
(relation_engine) birbirine bağlar ve veritabanına idempotent (yinelenemez)
olarak sürüm bilgisiyle (`s3.v1`) yazar.
"""

from __future__ import annotations

import json

from politikdesk.db import connection
from politikdesk.observability import get_logger
from politikdesk.political_memory.candidate_filter import (
    DEFAULT_CANDIDATE_LIMIT,
    extract_key_entities_from_text,
    fetch_candidate_events_from_db,
)
from politikdesk.political_memory.relation_engine import (
    EventData,
    RelationResult,
    evaluate_relation,
)

log = get_logger(__name__)

RELATION_ENGINE_VERSION = "s3.v1"


def evaluate_and_record_relations_for_event(
    source_event_id: int,
    candidate_events: list[EventData] | None = None,
    *,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
) -> list[RelationResult]:
    """Tekil bir olay için adayları çeker, değerlendirir ve idempotent kaydeder."""
    # 1. Kaynak olayı ve iddialarını çek
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, first_reported_at, vertical, topic_tags
            FROM events
            WHERE id = %s AND merged_into_id IS NULL;
            """,
            (source_event_id,),
        )
        src_row = cur.fetchone()
        if not src_row:
            return []

        cur.execute(
            """
            SELECT id, claim_text, claim_type, status_reason
            FROM claims
            WHERE event_id = %s;
            """,
            (source_event_id,),
        )
        src_claims = [dict(r) for r in cur.fetchall()]

        src_topics = tuple(src_row["topic_tags"]) if src_row.get("topic_tags") else ()

        cur.execute(
            """
            SELECT e.canonical_name, e.entity_type
            FROM event_entities ee
            JOIN entities e ON e.id = ee.entity_id
            WHERE ee.event_id = %s;
            """,
            (source_event_id,),
        )
        src_entities = cur.fetchall()

    src_actor = None
    src_inst = None
    for ent in src_entities:
        if ent["entity_type"] == "person" and not src_actor:
            src_actor = ent["canonical_name"]
        elif ent["entity_type"] == "institution" and not src_inst:
            src_inst = ent["canonical_name"]

    if not src_actor:
        for c in src_claims:
            reason = c.get("status_reason")
            if isinstance(reason, dict) and reason.get("speaker"):
                src_actor = reason["speaker"]
                break

    if not src_inst:
        for c in src_claims:
            reason = c.get("status_reason")
            if isinstance(reason, dict):
                if reason.get("institution"):
                    src_inst = reason["institution"]
                    break
                elif reason.get("speaker") and any(
                    k in reason["speaker"]
                    for k in ("Cumhurbaşkanlığı", "TBMM", "Sayıştay", "Bakanlık")
                ):
                    src_inst = reason["speaker"]
                    break

    src_entities_set = frozenset(ent["canonical_name"] for ent in src_entities)
    src_key_entities = extract_key_entities_from_text(src_row["title"], src_claims)

    source_data = EventData(
        event_id=src_row["id"],
        title=src_row["title"],
        published_at=src_row["first_reported_at"],
        actor=src_actor,
        institution=src_inst,
        entities=src_entities_set,
        key_entities=src_key_entities,
        topics=src_topics,
        claims=tuple(src_claims),
        vertical=src_row["vertical"],
    )

    # 2. Aday olayları hazırla
    candidates = candidate_events
    if candidates is None:
        candidates = fetch_candidate_events_from_db(source_event_id, limit=candidate_limit)

    if not candidates:
        return []

    results: list[RelationResult] = []

    # 3. Deterministik değerlendirme ve crash-safe per-candidate idempotent kayıt
    for cand in candidates:
        try:
            res = evaluate_relation(source_data, cand)
            if res.is_valid:
                results.append(res)
                # Per-candidate commit for crash-safety and partial result durability
                with connection() as conn, conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO event_relations (
                            from_event_id, to_event_id, relation, similarity, created_by,
                            confidence, evidence_payload, status, engine_version, updated_at
                        )
                        VALUES (%s, %s, %s, %s, 'system', %s, %s, %s, %s, now())
                        ON CONFLICT (from_event_id, to_event_id, relation) DO UPDATE
                        SET similarity = EXCLUDED.similarity,
                            confidence = EXCLUDED.confidence,
                            evidence_payload = EXCLUDED.evidence_payload,
                            status = EXCLUDED.status,
                            engine_version = EXCLUDED.engine_version,
                            updated_at = now();
                        """,
                        (
                            res.source_event_id,
                            res.target_event_id,
                            res.relation_type,
                            res.confidence,
                            res.confidence,
                            json.dumps(res.evidence_payload),
                            res.status,
                            RELATION_ENGINE_VERSION,
                        ),
                    )
                    conn.commit()
        except Exception as exc:
            log.error(
                "relation_evaluation_candidate_failed",
                source_event_id=source_event_id,
                target_event_id=cand.event_id,
                error=str(exc),
            )

    log.info(
        "political_relations_orchestrated",
        source_event_id=source_event_id,
        candidates_count=len(candidates),
        relations_found=len(results),
        engine_version=RELATION_ENGINE_VERSION,
    )
    return results


def process_pending_political_relations(limit: int = 50) -> dict[str, int]:
    """Canlı boru hattında bekleyen siyasi olaylar için ilişki çıkarma turu."""
    with connection() as conn, conn.cursor() as cur:
        # Reprocessing guard: Halihazırda bu motor versiyonuyla taranmış ve
        # son update'inden sonra değişmemiş olayları atla
        cur.execute(
            """
            SELECT e.id

            FROM events e
            WHERE e.merged_into_id IS NULL
              AND (
                  e.vertical = 'legislation'
                  OR EXISTS (
                      SELECT 1 FROM claims c
                      WHERE c.event_id = e.id AND c.claim_type = 'promise'
                  )
              )
              AND NOT EXISTS (
                  SELECT 1 FROM event_relations r
                  WHERE r.from_event_id = e.id
                    AND r.engine_version = %s
                    AND r.updated_at >= e.last_update_at
              )
            ORDER BY e.last_update_at DESC
            LIMIT %s;
            """,
            (RELATION_ENGINE_VERSION, limit),
        )
        rows = cur.fetchall()

    event_ids = [r["id"] for r in rows]
    total_relations = 0

    for eid in event_ids:
        found = evaluate_and_record_relations_for_event(eid)
        total_relations += len(found)

    stats = {
        "events_processed": len(event_ids),
        "relations_recorded": total_relations,
    }
    log.info("political_relations_batch_completed", **stats)
    return stats
