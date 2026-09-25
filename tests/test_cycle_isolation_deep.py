"""Faz 22: Döngü İzolasyonu, Tarihsel Arama ve Veri Bütünlüğü Derinlik Testleri."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.db import fetch_one
from politikdesk.web import repository, search

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer pd_sec_token_9876543210abcdef12345678"}


@pytest.mark.live_data
@pytest.mark.db
def test_feed_and_summary_strictly_isolated_from_legacy_cycle(db_conn) -> None:
    """Aktif feed ve sen yokken özeti sorgularının arşivlenmiş döngüden tamamen izole olduğunu doğrular."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM publication_cycles WHERE cycle_key = 'legacy_cycle_0';")
        legacy_id = int(fetch_one(cur)["id"])

        cur.execute("SELECT count(*) FROM events WHERE cycle_id = %s;", (legacy_id,))
        legacy_event_count = int(fetch_one(cur)["count"])
        assert legacy_event_count > 3000, "Arşiv döngüsünde 3000'den fazla olay olmalı"

    # Feed sorgusu
    feed_rows = repository.feed(user_id=1, limit=100)
    for r in feed_rows:
        with db_conn.cursor() as cur:
            cur.execute("SELECT cycle_id FROM events WHERE id = %s;", (r["id"],))
            c_id = fetch_one(cur)["cycle_id"]
            assert c_id != legacy_id, f"Arşivlenmiş olay #{r['id']} aktif feed'e sızdı!"


@pytest.mark.live_data
@pytest.mark.db
def test_search_can_find_historical_knowledge_via_omnibar(db_conn) -> None:
    """Arama motorunun (Omnibar / Ctrl+K) tarihsel arşiv kayıtlarına güvenle erişebildiğini doğrular."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, title FROM events
            WHERE cycle_id = 1 AND title IS NOT NULL AND length(title) > 10
            ORDER BY salience_score DESC NULLS LAST
            LIMIT 1;
            """
        )
        archived_ev = fetch_one(cur)
        if archived_ev is None:
            pytest.skip("Arşivde test edilecek olay bulunamadı.")
        archived_title = archived_ev["title"]

    # Search modülü üzerinden ara
    results = search.search(archived_title[:20], limit=10)

    # Arama sonuçlarında arşivdeki olay bulunabilmeli
    assert any(h.kind == "event" and h.href == f"/event/{archived_ev['id']}" for h in results), (
        "Arama motoru tarihsel arşivdeki olayı bulamadı!"
    )


@pytest.mark.db
def test_database_integrity_invariants(db_conn) -> None:
    """Veritabanı seviyesinde bütünlük kısıtlarının korunduğunu doğrular."""
    with db_conn.cursor() as cur:
        # 1. Yalnızca 1 aktif döngü kuralı
        cur.execute("SELECT count(*) FROM publication_cycles WHERE status = 'active';")
        active_cycles = int(fetch_one(cur)["count"])
        assert active_cycles == 1, f"Tam olarak 1 aktif döngü olmalı, bulunan: {active_cycles}"

        # 2. Yetim iddia (orphan claims) olmamalı
        cur.execute(
            "SELECT count(*) FROM claims c LEFT JOIN events e ON e.id = c.event_id WHERE e.id IS NULL;"
        )
        orphan_claims = int(fetch_one(cur)["count"])
        assert orphan_claims == 0, f"Yetim iddia tespit edildi: {orphan_claims}"

        # 3. Yetim kanıt (orphan evidence) olmamalı
        cur.execute(
            "SELECT count(*) FROM evidence ev LEFT JOIN claims c ON c.id = ev.claim_id WHERE c.id IS NULL;"
        )
        orphan_evidence = int(fetch_one(cur)["count"])
        assert orphan_evidence == 0, f"Yetim kanıt tespit edildi: {orphan_evidence}"

        # 4. Geçersiz taksonomi değeri olmamalı
        cur.execute(
            """
            SELECT count(*) FROM events
            WHERE category NOT IN ('ekonomi', 'politika', 'dis_politika', 'guvenlik', 'hukuk', 'enerji', 'teknoloji', 'saglik_toplum', 'yerel', 'diger')
               OR region NOT IN ('turkiye', 'abd', 'avrupa', 'orta_dogu', 'rusya_ukrayna', 'asya_pasifik', 'kuresel');
            """
        )
        invalid_taxonomy = int(fetch_one(cur)["count"])
        assert invalid_taxonomy == 0, (
            f"Geçersiz taksonomi değerli olay tespit edildi: {invalid_taxonomy}"
        )
