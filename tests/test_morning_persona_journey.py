"""Faz 22: Sabah Kullanıcı Deneyimi Senaryosu (Morning Persona Journey) Uçtan Uca Doğrulama Testi."""

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
from politikdesk.web import repository, search

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer pd_sec_token_9876543210abcdef12345678"}


@pytest.mark.db
def test_complete_morning_journalist_persona_journey(db_conn) -> None:
    """Kullanıcının sabah masaya oturup Gündem V2'yi kullandığı 18 adımlı gerçek senaryo testi."""
    now = datetime.now(UTC)

    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM publication_cycles WHERE status = 'active';")
        active_cycle_id = int(fetch_one(cur)["id"])
        cur.execute("SELECT id, slug, independence_group FROM sources WHERE is_active LIMIT 1;")
        src_row = fetch_one(cur)
        source_id = int(src_row["id"])
        source_slug = str(src_row["slug"])
        group = str(src_row["independence_group"] or source_slug)

    # 1. Gündem ekranına geliyor (HTTP GET /gundem)
    r1 = client.get("/gundem", headers=AUTH_HEADERS)
    assert r1.status_code == 200
    assert "Gündem V2 — Live Intelligence Feed" in r1.text

    # 2. "En Yeni"yi seçiyor (/api/feed?sort=newest)
    r2 = client.get("/api/feed?sort=newest", headers=AUTH_HEADERS)
    assert r2.status_code == 200
    assert r2.json()["sort"] == "newest"

    # 3. "Ekonomi" kategorisini seçiyor
    r3 = client.get("/api/feed?sort=newest&category=ekonomi", headers=AUTH_HEADERS)
    assert r3.status_code == 200
    assert r3.json()["filters"]["category"] == "ekonomi"

    # 4. "Türkiye" bölgesini ve son 24 saati seçiyor
    r4 = client.get(
        "/api/feed?sort=newest&category=ekonomi&region=turkiye&time_range=24h",
        headers=AUTH_HEADERS,
    )
    assert r4.status_code == 200
    f = r4.json()["filters"]
    assert f["category"] == "ekonomi"
    assert f["region"] == "turkiye"
    assert f["time_range"] == "24h"

    # 5. Sayfayı refresh ediyor / URL'i açıyor (State Persistence)
    r5 = client.get(
        "/gundem?sort=newest&category=ekonomi&region=turkiye&range=24h",
        headers=AUTH_HEADERS,
    )
    assert r5.status_code == 200
    html5 = r5.text
    assert 'value="ekonomi" selected' in html5
    assert 'value="turkiye" selected' in html5
    assert 'value="24h" selected' in html5

    # 6. Yeni bir haber ingestion pipeline'ından geliyor
    unique_url = f"https://journey-test.politikdesk.com/haber-{now.timestamp()}"
    title = "TCMB Haftalık Repo İhalesinde Faiz Oranını Sabit Tuttu"
    excerpt = "Para Politikası Kurulu faiz kararının ardından piyasa likiditesini yönetiyor."

    article = NormalizedArticle(
        source_slug=source_slug,
        canonical_url=unique_url,
        title=title,
        excerpt=excerpt,
        lead_paragraph="Detaylar...",
        published_at=now,
        content_hash=f"hash_j_{now.timestamp()}",
        simhash=555666777,
        lang="tr",
        topics=("politika_faizi", "enflasyon"),
        raw_purge_at=now + timedelta(days=7),
        official_value=None,
        vertical="macro_economy",
    )
    art_id = insert_article(article, source_id=source_id, independence_key=group)
    assert art_id is not None

    created_event_id: int | None = None
    try:
        # Kümeleme ile olay oluşuyor
        features = ArticleFeatures(
            article_id=art_id,
            embedding=[0.02] * 1024,
            entities=frozenset(["TCMB", "PPK"]),
            key_entities=frozenset(["TCMB"]),
            published_at=now,
            vertical="macro_economy",
        )
        created_event_id = create_event(features, {"title": title, "excerpt": excerpt})
        assert created_event_id is not None

        # 7. Kullanıcı "X yeni gelişme" polling denetimini tetikliyor
        past_ts = (now - timedelta(seconds=10)).isoformat()
        r_check = client.get(f"/api/feed/check-new?since={past_ts}", headers=AUTH_HEADERS)
        assert r_check.status_code == 200
        assert r_check.json()["new_count"] >= 1

        # 8. Yeni haber feed'e eklendiğinde [YENİ] etiketiyle geliyor
        feed_rows = repository.feed(user_id=1, sort="newest", category="ekonomi")
        matching = [x for x in feed_rows if x["id"] == created_event_id]
        assert len(matching) == 1
        assert matching[0]["is_new"] is True

        # 9. Kullanıcı "Önemli" moduna geçiyor
        r_imp = client.get("/api/feed?sort=important&category=ekonomi", headers=AUTH_HEADERS)
        assert r_imp.status_code == 200
        assert r_imp.json()["sort"] == "important"

        # 10. Arama yapıyor (Omnibar): Tarihsel arşivdeki verilere erişebiliyor
        with db_conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title FROM events
                WHERE cycle_id = 1 AND length(title) > 10
                ORDER BY salience_score DESC NULLS LAST
                LIMIT 1;
                """
            )
            archived = fetch_one(cur)
        if archived:
            words = [w for w in archived["title"].split() if len(w) >= 4]
            search_term = words[0] if words else archived["title"][:10]
            search_hits = search.search(search_term, limit=10)
            assert len(search_hits) > 0
            assert any(h.kind == "event" for h in search_hits)

        # 11. Gündem ekranı ise yalnızca aktif döngü verilerini gösteriyor
        for row in feed_rows:
            with db_conn.cursor() as cur:
                cur.execute("SELECT cycle_id FROM events WHERE id = %s;", (row["id"],))
                cid = fetch_one(cur)["cycle_id"]
                assert cid == active_cycle_id

    finally:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM articles WHERE id = %s;", (art_id,))
            if created_event_id:
                cur.execute("DELETE FROM events WHERE id = %s;", (created_event_id,))
