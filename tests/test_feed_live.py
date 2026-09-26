"""Faz 22: Canlı İstihbarat Akışı (Live Feed), Bildirim Banner'ı ve Polling Testleri."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.db import fetch_one

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer pd_sec_token_9876543210abcdef12345678"}


@pytest.mark.db
def test_check_new_events_polling_api(db_conn) -> None:
    """/api/feed/check-new endpoint'inin canlı olayları tespit edip arşiv olaylarını izole ettiğini doğrular."""
    now = datetime.now(UTC)
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM publication_cycles WHERE status = 'active';")
        active_id = int(fetch_one(cur)["id"])
        cur.execute("SELECT id FROM publication_cycles WHERE cycle_key = 'legacy_cycle_0';")
        legacy_id = int(fetch_one(cur)["id"])

    # 1. Başlangıçta yeni olay yok
    resp_init = client.get(
        f"/api/feed/check-new?since={now.isoformat()}",
        headers=AUTH_HEADERS,
    )
    assert resp_init.status_code == 200
    assert resp_init.json()["new_count"] == 0

    # 2. Aktif döngüye 2 yeni olay ekle, Arşiv döngüsüne 1 olay ekle
    created_eids: list[int] = []
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (title, summary, vertical, category, region, salience_score, first_reported_at, last_update_at, cycle_id)
                VALUES
                  ('Canlı Aktif Olay 1', 'Özet 1', 'macro_economy', 'ekonomi', 'turkiye', 50, now() + interval '1 second', now() + interval '1 second', %s),
                  ('Canlı Aktif Olay 2', 'Özet 2', 'macro_economy', 'teknoloji', 'abd', 60, now() + interval '2 seconds', now() + interval '2 seconds', %s),
                  ('Arşivlenmiş Eski Olay', 'Özet Arşiv', 'macro_economy', 'politika', 'turkiye', 90, now() + interval '3 seconds', now() + interval '3 seconds', %s)
                RETURNING id;
                """,
                (active_id, active_id, legacy_id),
            )
            created_eids = [r["id"] for r in cur.fetchall()]

        # 3. Polling API çağır
        resp_poll = client.get(
            f"/api/feed/check-new?since={now.isoformat()}",
            headers=AUTH_HEADERS,
        )
        assert resp_poll.status_code == 200
        poll_data = resp_poll.json()

        # Yalnızca aktif döngüdeki 2 olay dönmeli (Arşiv olayı sızmamalı)
        assert poll_data["new_count"] == 2
        assert poll_data["since"] is not None

    finally:
        if created_eids:
            with db_conn.cursor() as cur:
                cur.execute("DELETE FROM events WHERE id = ANY(%s);", (created_eids,))


def test_live_feed_ui_components_and_script_elements() -> None:
    """Gündem V2 HTML arayüzünün canlı banner ve JavaScript bileşenlerini içerdiğini doğrular."""
    resp = client.get(
        "/gundem?sort=newest&category=ekonomi&region=turkiye&range=24h",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    html = resp.text

    # 1. Başlık ve Canlı Masa Göstergeleri
    assert "<h1 class=\"page-title\">Gündem</h1>" in html or ">Gündem</h1>" in html
    assert "feed-new-banner" in html
    assert "feed-toolbar" in html

    # 2. Sıralama ve Filtre Düğmeleri
    assert "sort=newest" in html
    assert "sort=important" in html
    assert "sort=updated" in html
    # Kategori/bölge çip olarak (tekrarlanan açılır menü kaldırıldı)
    assert "category=" in html
    assert 'id="filter-category"' not in html
    assert 'id="filter-range"' in html

    # 3. Canlı Polling ve Sıçramasız Ekleme Betiği
    assert "pdCheckNew" in html
    assert "/api/feed/check-new" in html
    assert "pdApplyFilters" in html
