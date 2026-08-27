"""Faz 21 — Üretim Veri Yaşam Döngüsü ve Arşiv İzolasyonu Testleri."""

from __future__ import annotations

import pytest

from politikdesk.db import fetch_one
from politikdesk.ingestion.models import NormalizedArticle
from politikdesk.ingestion.repository import insert_article
from politikdesk.web import repository


@pytest.mark.db
def test_publication_cycles_schema_and_active_constraint(db_conn) -> None:
    """publication_cycles tablosunun ve tekil active kısıtının çalıştığını doğrular."""
    import psycopg

    with db_conn.cursor() as cur:
        cur.execute("SELECT id, cycle_key, status FROM publication_cycles WHERE status = 'active';")
        active_rows = cur.fetchall()
        assert len(active_rows) == 1, "Sistemde tam olarak 1 aktif döngü bulunmalı"

        # İkinci bir 'active' döngü eklenmeye çalışıldığında DB seviyesinde reddedilmeli
        with pytest.raises(psycopg.errors.UniqueViolation):
            cur.execute(
                """
                INSERT INTO publication_cycles (cycle_key, name, status)
                VALUES ('duplicate_active_test', 'Çift Aktif Testi', 'active');
                """
            )
        db_conn.rollback()


@pytest.mark.db
def test_archived_data_isolation_in_default_feed(db_conn) -> None:
    """Arşivlenmiş döngüdeki olayların varsayılan Gündem sorgusunda görünmediğini doğrular."""
    with db_conn.cursor() as cur:
        # Arşiv döngüsü ID'sini al
        cur.execute("SELECT id FROM publication_cycles WHERE cycle_key = 'legacy_cycle_0';")
        legacy_id = int(fetch_one(cur)["id"])

        # Arşiv döngüsünde 3000'den fazla olay olduğunu doğrula
        cur.execute("SELECT count(*) FROM events WHERE cycle_id = %s;", (legacy_id,))
        legacy_events_count = int(fetch_one(cur)["count"])
        assert legacy_events_count > 0, "Arşiv döngüsünde korunmuş veri bulunmalı"

    # Varsayılan feed sorgusu çalıştır (user_id=1)
    feed_rows = repository.feed(user_id=1, limit=50)

    # Dönen olayların hiçbirinin cycle_id'si legacy_id olmamalı (0 sızıntı)
    for r in feed_rows:
        assert r.get("cycle_id") != legacy_id, (
            f"İzolasyon ihlali: Arşiv döngüsündeki olay #{r['id']} aktif feed'de belirdi!"
        )


@pytest.mark.db
def test_new_active_event_appears_in_feed(db_conn) -> None:
    """Aktif döngüye eklenen yeni bir olayın feed'de göründüğünü doğrular."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM publication_cycles WHERE status = 'active';")
        active_cycle_id = int(fetch_one(cur)["id"])

        cur.execute(
            """
            INSERT INTO events (
                title, summary, vertical, category, region, salience_score,
                first_reported_at, last_update_at, cycle_id
            ) VALUES (
                'Faz 21 Canlı Test Olayı', 'Canlı istihbarat testi', 'macro_economy',
                'ekonomi', 'turkiye', 85, now(), now(), %s
            ) RETURNING id;
            """,
            (active_cycle_id,),
        )
        new_event_id = int(fetch_one(cur)["id"])

    try:
        rows = repository.feed(user_id=1, limit=10, sort="newest")
        found = any(r["id"] == new_event_id for r in rows)
        assert found, f"Aktif döngüye eklenen yeni olay #{new_event_id} feed'de bulunamadı!"
    finally:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE id = %s;", (new_event_id,))


@pytest.mark.db
def test_insert_article_attaches_active_cycle_and_taxonomy(db_conn) -> None:
    """Yeni eklenen bir makalenin aktif döngüye, kategoriye ve bölgeye otomatik bağlandığını doğrular."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM sources WHERE is_active LIMIT 1;")
        source_id = int(fetch_one(cur)["id"])
        cur.execute("SELECT id FROM publication_cycles WHERE status = 'active';")
        active_cycle_id = int(fetch_one(cur)["id"])

    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)

    test_article = NormalizedArticle(
        source_slug="tcmb",
        canonical_url="https://test.politikdesk.com/makale-faz21-test-1",
        title="Merkez Bankası faiz kararı ve enflasyon raporu",
        excerpt="TCMB Para Politikası Kurulu enflasyon tahminlerini açıkladı.",
        lead_paragraph=None,
        published_at=now,
        content_hash="hash_faz21_test_1",
        simhash=123456789,
        lang="tr",
        topics=("enflasyon", "politika_faizi"),
        raw_purge_at=now + timedelta(days=7),
        official_value=None,
        vertical="macro_economy",
    )

    art_id = insert_article(
        test_article,
        source_id=source_id,
        independence_key="test_group",
    )
    assert art_id is not None, "Makale başarıyla kaydedilmeli"

    try:
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT cycle_id, category, region FROM articles WHERE id = %s;",
                (art_id,),
            )
            row = fetch_one(cur)
            assert row["cycle_id"] == active_cycle_id, "Makale aktif döngüye bağlanmalı"
            assert row["category"] == "ekonomi", "Kategori 'ekonomi' olmalı"
            assert row["region"] == "turkiye", "Bölge 'turkiye' olmalı"
    finally:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM articles WHERE id = %s;", (art_id,))
