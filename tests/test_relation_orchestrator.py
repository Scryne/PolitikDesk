"""S3 Relation Orchestrator ve Idempotency Testleri (Spec v3.4 §14.1)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from politikdesk.political_memory.orchestrator import (
    RELATION_ENGINE_VERSION,
    evaluate_and_record_relations_for_event,
)
from politikdesk.political_memory.relation_engine import EventData


@pytest.mark.db
def test_relation_orchestrator_idempotent_execution() -> None:
    """Aynı olayın 5 kez değerlendirilmesi durumunda duplicate relation oluşmadığını doğrular."""
    from politikdesk.db import connection

    with connection() as conn, conn.cursor() as cur:
        # 2 test olayı ve 1 vaat iddiası ekle
        cur.execute(
            """
            INSERT INTO events (title, first_reported_at, last_update_at, vertical, topic_tags)
            VALUES ('Cumhurbaşkanlığı Açıklaması: Kamuda Mülakat Uygulamasının Kaldırılması Planlanıyor', now() - interval '1 day', now() - interval '1 day', 'legislation', ARRAY['kamu_istihdami', 'yasama_sureci'])
            RETURNING id;
            """
        )
        e1 = cur.fetchone()["id"]

        cur.execute(
            """
            INSERT INTO claims (event_id, claim_text, claim_type, evidence_status, status_reason)
            VALUES (%s, 'Kamuda mülakat kaldırılacak', 'promise', 'attribution_verified', '{"speaker": "Cumhurbaşkanlığı"}'::jsonb)
            RETURNING id;
            """,
            (e1,),
        )

        cur.execute(
            """
            INSERT INTO events (title, first_reported_at, last_update_at, vertical, topic_tags)
            VALUES ('Kamuda Mülakatın Kaldırılmasına Dair Kanun Teklifi TBMM Genel Kurulunda Kabul Edildi', now(), now(), 'legislation', ARRAY['kamu_istihdami', 'yasama_sureci'])
            RETURNING id;
            """
        )
        e2 = cur.fetchone()["id"]
        conn.commit()

    try:
        cand = EventData(
            event_id=e2,
            title="Kamuda Mülakatın Kaldırılmasına Dair 7520 Sayılı Kanun Teklifi TBMM Genel Kurulunda Kabul Edildi",
            published_at=datetime.now(UTC),
            actor="TBMM",
            institution="TBMM",
            topics=("kamu_istihdami", "yasama_sureci"),
            key_entities=frozenset({"mülakat", "7520"}),
            claims=({"claim_text": "Kanun kabul edildi", "claim_type": "fact"},),
            vertical="legislation",
        )

        # 1. Koşum
        res1 = evaluate_and_record_relations_for_event(e1, candidate_events=[cand])
        assert len(res1) == 1

        # 2., 3., 4., 5. Koşum (Idempotency testi)
        for _ in range(4):
            res_repeat = evaluate_and_record_relations_for_event(e1, candidate_events=[cand])
            assert len(res_repeat) == 1

        # Veritabanında tam olarak 1 adet ilişki satırı olmalı
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*) as count, relation, engine_version, status
                FROM event_relations
                WHERE from_event_id = %s AND to_event_id = %s
                GROUP BY relation, engine_version, status;
                """,
                (e1, e2),
            )
            rows = cur.fetchall()
            assert len(rows) == 1
            assert rows[0]["count"] == 1
            assert rows[0]["relation"] == "fulfils"
            assert rows[0]["engine_version"] == RELATION_ENGINE_VERSION
            assert rows[0]["status"] in ("verified", "supported", "inferred")

    finally:
        with connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM event_relations WHERE from_event_id = %s;", (e1,))
            cur.execute("DELETE FROM claims WHERE event_id = %s;", (e1,))
            cur.execute("DELETE FROM articles WHERE event_id = %s;", (e1,))
            cur.execute("DELETE FROM events WHERE id IN (%s, %s);", (e1, e2))
            conn.commit()


@pytest.mark.db
def test_concurrent_orchestrator_execution() -> None:
    """Eşzamanlı (concurrent) çalışan birden fazla worker aynı olayı işlediğinde veri bütünlüğü ve tekillik korunur."""
    import concurrent.futures

    from politikdesk.db import connection

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO events (title, first_reported_at, last_update_at, vertical, topic_tags)
            VALUES ('Cumhurbaşkanlığı Açıklaması: Kamuda Mülakat Uygulamasının Kaldırılması Planlanıyor', now() - interval '1 day', now() - interval '1 day', 'legislation', ARRAY['kamu_istihdami'])
            RETURNING id;
            """
        )
        e1 = cur.fetchone()["id"]

        cur.execute(
            """
            INSERT INTO claims (event_id, claim_text, claim_type, evidence_status, status_reason)
            VALUES (%s, 'Kamuda mülakat kaldırılacak', 'promise', 'attribution_verified', '{"speaker": "Cumhurbaşkanlığı"}'::jsonb)
            RETURNING id;
            """,
            (e1,),
        )

        cur.execute(
            """
            INSERT INTO events (title, first_reported_at, last_update_at, vertical, topic_tags)
            VALUES ('Kamuda Mülakatın Kaldırılmasına Dair Kanun Teklifi TBMM Genel Kurulunda Kabul Edildi', now(), now(), 'legislation', ARRAY['kamu_istihdami'])
            RETURNING id;
            """
        )
        e2 = cur.fetchone()["id"]
        conn.commit()

    try:
        cand = EventData(
            event_id=e2,
            title="Kamuda Mülakatın Kaldırılmasına Dair 7520 Sayılı Kanun Teklifi TBMM Genel Kurulunda Kabul Edildi",
            published_at=datetime.now(UTC),
            actor="TBMM",
            institution="TBMM",
            topics=("kamu_istihdami",),
            key_entities=frozenset({"mülakat", "7520"}),
            claims=({"claim_text": "Kanun kabul edildi", "claim_type": "fact"},),
            vertical="legislation",
        )

        def worker_task() -> int:
            res = evaluate_and_record_relations_for_event(e1, candidate_events=[cand])
            return len(res)

        # 4 eşzamanlı thread ile yarış durumu (race-condition) simülasyonu
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker_task) for _ in range(4)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(r == 1 for r in results)

        # DB'de tam olarak 1 tekil ilişki bulunmalı (idempotency & concurrency safe)
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*) as count, relation, engine_version
                FROM event_relations
                WHERE from_event_id = %s AND to_event_id = %s
                GROUP BY relation, engine_version;
                """,
                (e1, e2),
            )
            rows = cur.fetchall()
            assert len(rows) == 1
            assert rows[0]["count"] == 1
            assert rows[0]["relation"] == "fulfils"
            assert rows[0]["engine_version"] == RELATION_ENGINE_VERSION

    finally:
        with connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM event_relations WHERE from_event_id = %s;", (e1,))
            cur.execute("DELETE FROM claims WHERE event_id = %s;", (e1,))
            cur.execute("DELETE FROM articles WHERE event_id = %s;", (e1,))
            cur.execute("DELETE FROM events WHERE id IN (%s, %s);", (e1, e2))
            conn.commit()
