"""Faz 22: Gerçek Ingestion Pipeline, Taksonomi ve Aktif Döngü Entegrasyon Testi."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.clustering.assigner import ArticleFeatures
from politikdesk.clustering.repository import create_event
from politikdesk.db import fetch_one
from politikdesk.ingestion.models import NormalizedArticle
from politikdesk.ingestion.repository import insert_article
from politikdesk.web import repository

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer pd_sec_token_9876543210abcdef12345678"}


@pytest.mark.db
def test_full_ingestion_to_feed_pipeline(db_conn) -> None:
    """Uçtan uca Ingestion -> Event -> Feed akışını ve aktif döngü izolasyonunu doğrular.

    Akış:
      SOURCE -> NORMALIZATION -> INSERT_ARTICLE (auto taxonomy + auto cycle)
      -> CREATE_EVENT -> REPOSITORY.FEED -> API.
    """
    now = datetime.now(UTC)
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM publication_cycles WHERE status = 'active';")
        active_cycle_id = int(fetch_one(cur)["id"])
        cur.execute("SELECT id, slug, independence_group FROM sources WHERE is_active LIMIT 1;")
        source_row = fetch_one(cur)
        source_id = int(source_row["id"])
        source_slug = str(source_row["slug"])
        group = str(source_row["independence_group"] or source_slug)

    unique_url = f"https://live-test.politikdesk.com/makale-canli-{now.timestamp()}"
    title = "Hazine ve Maliye Bakanlığı Yeni Vergi Paketi Taslağını TBMM'ye Sundu"
    excerpt = "Bakanlık vergi reformu kapsamında doğrudan vergilerin payını artırmayı hedefliyor."

    test_article = NormalizedArticle(
        source_slug=source_slug,
        canonical_url=unique_url,
        title=title,
        excerpt=excerpt,
        lead_paragraph="Detaylı vergi paketi açıklaması...",
        published_at=now,
        content_hash=f"hash_{now.timestamp()}",
        simhash=987654321,
        lang="tr",
        topics=("vergi_ve_harclar", "butce"),
        raw_purge_at=now + timedelta(days=7),
        official_value=None,
        vertical="macro_economy",
    )

    # 1. Insert Article
    art_id = insert_article(test_article, source_id=source_id, independence_key=group)
    assert art_id is not None, "Makale başarıyla DB'ye eklenmeli"

    # Idempotency testi (Duplicate URL engeli)
    dup_art_id = insert_article(test_article, source_id=source_id, independence_key=group)
    assert dup_art_id is None, "Aynı URL tekrar eklendiğinde None dönmeli (idempotent)"

    created_event_id: int | None = None
    try:
        # DB'deki alanları doğrula
        with db_conn.cursor() as cur:
            cur.execute("SELECT cycle_id, category, region FROM articles WHERE id = %s;", (art_id,))
            a_row = fetch_one(cur)
            assert a_row["cycle_id"] == active_cycle_id, "Makale aktif döngüye bağlanmalı"
            assert a_row["category"] == "ekonomi", "Kategori 'ekonomi' olarak tespit edilmeli"
            assert a_row["region"] == "turkiye", "Bölge 'turkiye' olarak tespit edilmeli"

        # 2. Create Event (Clustering)
        features = ArticleFeatures(
            article_id=art_id,
            embedding=[0.05] * 1024,
            entities=frozenset(["Hazine ve Maliye Bakanlığı", "TBMM"]),
            key_entities=frozenset(["Hazine ve Maliye Bakanlığı"]),
            published_at=now,
            vertical="macro_economy",
        )
        created_event_id = create_event(features, {"title": title, "excerpt": excerpt})
        assert created_event_id is not None, "Olay başarıyla oluşturulmalı"

        # Olay alanlarını doğrula
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT cycle_id, category, region, article_count FROM events WHERE id = %s;",
                (created_event_id,),
            )
            ev_row = fetch_one(cur)
            assert ev_row["cycle_id"] == active_cycle_id, "Olay aktif döngüye bağlanmalı"
            assert ev_row["category"] == "ekonomi", "Olay kategorisi 'ekonomi' olmalı"
            assert ev_row["region"] == "turkiye", "Olay bölgesi 'turkiye' olmalı"
            assert ev_row["article_count"] == 1, "Makale sayısı 1 olmalı"

        # 3. Feed Sorgusunda Doğrulama
        feed_items = repository.feed(user_id=1, sort="newest", limit=20)
        matching_feed = [r for r in feed_items if r["id"] == created_event_id]
        assert len(matching_feed) == 1, "Olay feed'de yer almalı"
        feed_event = matching_feed[0]
        assert feed_event["category"] == "ekonomi"
        assert feed_event["region"] == "turkiye"
        assert feed_event["is_new"] is True, "Yeni oluşturulan olay 'is_new=True' olmalı"

        # 4. HTTP API Doğrulama
        resp = client.get("/api/feed?sort=newest&category=ekonomi", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        api_data = resp.json()
        assert any(x["id"] == created_event_id for x in api_data["items"])

        # 5. Check-New Doğrulama (Zaman damgası öncesi için yeni sayılmalı)
        past_ts = (now - timedelta(minutes=5)).isoformat()
        check_resp = client.get(f"/api/feed/check-new?since={past_ts}", headers=AUTH_HEADERS)
        assert check_resp.status_code == 200
        assert check_resp.json()["new_count"] >= 1

    finally:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM articles WHERE id = %s;", (art_id,))
            if created_event_id:
                cur.execute("DELETE FROM events WHERE id = %s;", (created_event_id,))
