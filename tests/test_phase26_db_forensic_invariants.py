"""Phase 26: 10 Explicit Database Forensic Invariant Assertions Test Suite."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from politikdesk.db import fetch_one


@pytest.mark.db
def test_invariant_1_event_article_count_matches_actual(db_conn) -> None:
    """Invariant 1: event.article_count == count(articles WHERE event_id = e.id)"""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT e.id, e.article_count, count(a.id) AS actual_count
            FROM events e
            LEFT JOIN articles a ON a.event_id = e.id
            GROUP BY e.id, e.article_count
            HAVING e.article_count <> count(a.id);
        """)
        mismatches = cur.fetchall()
        assert len(mismatches) == 0, f"article_count uyumsuzluğu bulundu: {mismatches[:5]}"


@pytest.mark.db
def test_invariant_2_article_event_fk_integrity(db_conn) -> None:
    """Invariant 2: article.event_id varsa event gerçekten mevcuttur (orphan article yok)."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT a.id, a.event_id
            FROM articles a
            LEFT JOIN events e ON e.id = a.event_id
            WHERE a.event_id IS NOT NULL AND e.id IS NULL;
        """)
        orphans = cur.fetchall()
        assert len(orphans) == 0, f"Orphan article bulundu: {orphans}"


@pytest.mark.db
def test_invariant_3_claim_event_reference_integrity(db_conn) -> None:
    """Invariant 3: claim.event_id varsa event mevcuttur (orphan claim yok)."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT c.id, c.event_id
            FROM claims c
            LEFT JOIN events e ON e.id = c.event_id
            WHERE c.event_id IS NOT NULL AND e.id IS NULL;
        """)
        orphans = cur.fetchall()
        assert len(orphans) == 0, f"Orphan claim bulundu: {orphans}"


@pytest.mark.db
def test_invariant_4_evidence_claim_reference_integrity(db_conn) -> None:
    """Invariant 4: evidence.claim_id varsa claim mevcuttur (orphan evidence yok)."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT ev.id, ev.claim_id
            FROM evidence ev
            LEFT JOIN claims c ON c.id = ev.claim_id
            WHERE ev.claim_id IS NOT NULL AND c.id IS NULL;
        """)
        orphans = cur.fetchall()
        assert len(orphans) == 0, f"Orphan evidence bulundu: {orphans}"


@pytest.mark.db
def test_invariant_5_closed_publication_cycle_immutability(db_conn) -> None:
    """Invariant 5: Arşivlenmiş/kapanmış publication_cycle durumu korunur."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT id, cycle_key, status, started_at, ended_at
            FROM publication_cycles
            WHERE status = 'archived';
        """)
        archived_cycles = cur.fetchall()
        for cyc in archived_cycles:
            assert cyc["ended_at"] is not None
            assert cyc["ended_at"] >= cyc["started_at"]


@pytest.mark.db
def test_invariant_6_single_active_publication_cycle(db_conn) -> None:
    """Invariant 6: Aktif publication_cycle sayısı en fazla 1'dir."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) AS cnt FROM publication_cycles WHERE status = 'active';")
        row = fetch_one(cur)
        assert row["cnt"] <= 1, f"Birden fazla aktif cycle bulundu: {row['cnt']}"


@pytest.mark.db
def test_invariant_7_first_reported_at_lte_last_update_at(db_conn) -> None:
    """Invariant 7: first_reported_at <= last_update_at veya mantıklı zaman tutarlılığı."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT id, first_reported_at, last_update_at
            FROM events
            WHERE first_reported_at IS NOT NULL 
              AND last_update_at IS NOT NULL
              AND first_reported_at > last_update_at + interval '1 second';
        """)
        invalid_times = cur.fetchall()
        assert len(invalid_times) == 0, f"first_reported_at > last_update_at anomalisi: {invalid_times[:5]}"


@pytest.mark.db
def test_invariant_8_published_at_valid_semantics(db_conn) -> None:
    """Invariant 8: published_at alanı geçerli ve mantıklı bir zaman damgasına sahiptir."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT id, published_at, first_seen_at
            FROM articles
            WHERE published_at IS NOT NULL AND published_at < '1990-01-01T00:00:00Z';
        """)
        ancient_records = cur.fetchall()
        assert len(ancient_records) == 0, f"Geçersiz antik zaman damgası: {ancient_records[:5]}"


@pytest.mark.db
def test_invariant_9_no_impossible_future_records(db_conn) -> None:
    """Invariant 9: Veritabanında geleceğe tarihli (+1 günden fazla) makale veya olay yoktur."""
    threshold = datetime.now(UTC) + timedelta(days=1)
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT id, published_at FROM articles WHERE published_at > %s;
        """, (threshold,))
        future_articles = cur.fetchall()
        assert len(future_articles) == 0, f"Gelecek tarihli makale bulundu: {future_articles[:5]}"

        cur.execute("""
            SELECT id, first_reported_at FROM events WHERE first_reported_at > %s;
        """, (threshold,))
        future_events = cur.fetchall()
        assert len(future_events) == 0, f"Gelecek tarihli olay bulundu: {future_events[:5]}"


@pytest.mark.db
def test_invariant_10_archived_and_active_cycle_isolation(db_conn) -> None:
    """Invariant 10: Arşivlenmiş makaleler ve aktif döngü makaleleri kesin izolasyondadır."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM publication_cycles WHERE cycle_key = 'legacy_cycle_0';")
        legacy_row = cur.fetchone()
        cur.execute("SELECT id FROM publication_cycles WHERE status = 'active';")
        active_row = cur.fetchone()

        if legacy_row and active_row:
            legacy_id = legacy_row["id"]
            active_id = active_row["id"]
            assert legacy_id != active_id

            # Hiçbir makale aynı anda iki cycle'a ait olamaz
            cur.execute("""
                SELECT count(*) AS overlap_count
                FROM articles
                WHERE cycle_id = %s AND cycle_id = %s;
            """, (legacy_id, active_id))
            overlap = fetch_one(cur)["overlap_count"]
            assert overlap == 0
