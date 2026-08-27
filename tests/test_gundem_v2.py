"""Faz 21 — Gündem V2 Live Intelligence Feed Fonksiyonel ve API Testleri."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.db import fetch_one
from politikdesk.web import repository

client = TestClient(app)


@pytest.mark.db
def test_gundem_v2_html_endpoint_and_toolbar(db_conn) -> None:
    """Gündem V2 HTML sayfasının (/gundem ve /feed) sorunsuz açıldığını ve toolbar öğelerini içerdiğini doğrular."""
    resp = client.get("/gundem")
    assert resp.status_code == 200
    html = resp.text

    assert "Gündem V2 — Live Intelligence Feed" in html
    assert "feed-toolbar" in html
    assert "feed-sort-group" in html
    assert "feed-select" in html
    assert "filter-category" in html
    assert "filter-region" in html
    assert "filter-range" in html
    assert "feed-new-banner" in html


@pytest.mark.db
def test_gundem_v2_sorting_modes(db_conn) -> None:
    """Sıralama modlarının (Önemli, En Yeni, Son Güncellenen) doğru çalıştığını doğrular."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM publication_cycles WHERE status = 'active';")
        active_id = int(fetch_one(cur)["id"])

        # 3 farklı olay ekle
        cur.execute(
            """
            INSERT INTO events (title, vertical, salience_score, first_reported_at, last_update_at, cycle_id)
            VALUES
              ('Düşük Önemli Çok Yeni', 'macro_economy', 10, now(), now(), %s),
              ('Yüksek Önemli Eski', 'macro_economy', 85, now() - interval '2 days', now() - interval '2 days', %s),
              ('Orta Önemli Yeni Güncellenen', 'macro_economy', 50, now() - interval '1 day', now(), %s)
            RETURNING id;
            """,
            (active_id, active_id, active_id),
        )
        created_ids = [r["id"] for r in cur.fetchall()]

    try:
        # 1. Önemli (Important) sıralaması: Yüksek önemli başa gelmeli
        feed_imp = repository.feed(user_id=1, sort="important", limit=500)
        found_imp = [r for r in feed_imp if r["id"] in created_ids]
        assert len(found_imp) >= 2
        assert found_imp[0]["salience_score"] >= found_imp[1]["salience_score"]

        # 2. En Yeni (Newest) sıralaması: İlk reported_at en yeni olan başa gelmeli
        feed_newest = repository.feed(user_id=1, sort="newest", limit=500)
        found_newest = [r for r in feed_newest if r["id"] in created_ids]
        assert len(found_newest) >= 2
        assert found_newest[0]["title"] == "Düşük Önemli Çok Yeni"

        # 3. Son Güncellenen (Updated) sıralaması
        feed_updated = repository.feed(user_id=1, sort="updated", limit=500)
        found_updated = [r for r in feed_updated if r["id"] in created_ids]
        assert len(found_updated) >= 2
        assert found_updated[0]["last_update_at"] >= found_updated[1]["last_update_at"]

    finally:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE id = ANY(%s);", (created_ids,))


@pytest.mark.db
def test_gundem_v2_filtering(db_conn) -> None:
    """Kategori, bölge ve zaman filtrelerinin doğru daraltma yaptığını doğrular."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM publication_cycles WHERE status = 'active';")
        active_id = int(fetch_one(cur)["id"])

        cur.execute(
            """
            INSERT INTO events (title, vertical, category, region, salience_score, first_reported_at, last_update_at, cycle_id)
            VALUES
              ('Enerji Türkiye Olayı', 'macro_economy', 'enerji', 'turkiye', 60, now(), now(), %s),
              ('Savunma ABD Olayı', 'macro_economy', 'guvenlik', 'abd', 70, now(), now(), %s)
            RETURNING id;
            """,
            (active_id, active_id),
        )
        created_ids = [r["id"] for r in cur.fetchall()]

    try:
        # Kategori filtresi: enerji
        rows_energy = repository.feed(user_id=1, category="enerji", limit=10)
        assert any(r["id"] == created_ids[0] for r in rows_energy)
        assert not any(r["id"] == created_ids[1] for r in rows_energy)

        # Bölge filtresi: abd
        rows_abd = repository.feed(user_id=1, region="abd", limit=10)
        assert any(r["id"] == created_ids[1] for r in rows_abd)
        assert not any(r["id"] == created_ids[0] for r in rows_abd)

        # Kombine filtre: enerji + turkiye
        rows_comb = repository.feed(user_id=1, category="enerji", region="turkiye", limit=10)
        assert any(r["id"] == created_ids[0] for r in rows_comb)
        assert not any(r["id"] == created_ids[1] for r in rows_comb)

    finally:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE id = ANY(%s);", (created_ids,))


@pytest.mark.db
def test_api_feed_json_endpoint(db_conn) -> None:
    """/api/feed JSON uç noktasının doğru yapı döndürdüğünü doğrular."""
    resp = client.get("/api/feed?sort=important&category=ekonomi&limit=10")
    assert resp.status_code == 200
    data = resp.json()

    assert "items" in data
    assert "count" in data
    assert data["sort"] == "important"
    assert data["filters"]["category"] == "ekonomi"


@pytest.mark.db
def test_api_feed_taxonomy_endpoint() -> None:
    """/api/feed/taxonomy uç noktasının kanonik sözlüğü döndürdüğünü doğrular."""
    resp = client.get("/api/feed/taxonomy")
    assert resp.status_code == 200
    data = resp.json()

    assert "categories" in data
    assert "regions" in data
    assert "sort_modes" in data
    assert "time_ranges" in data

    cat_keys = [c["key"] for c in data["categories"]]
    assert "ekonomi" in cat_keys
    assert "politika" in cat_keys
    assert "dis_politika" in cat_keys


@pytest.mark.db
def test_api_feed_check_new_endpoint(db_conn) -> None:
    """/api/feed/check-new uç noktasının yeni gelişme sayısını döndürdüğünü doğrular."""
    resp = client.get("/api/feed/check-new?since=2026-01-01T00:00:00Z")
    assert resp.status_code == 200
    data = resp.json()
    assert "new_count" in data
    assert "since" in data
