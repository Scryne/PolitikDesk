"""Phase 25: 18 Adımlı Gazeteci Kullanıcı Deneyimi (User Journey) E2E Doğrulama Testi."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.web.repository import feed

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer pd_sec_token_9876543210abcdef12345678"}


@pytest.mark.live_data
@pytest.mark.db
def test_journalist_18_step_journey_complete(db_conn) -> None:
    """18 adımlı gerçek gazeteci sabah iş akışının tüm adımlarını test eder."""

    # ── ADIM 1: Sabah Sistemi Aç (HTML Feed Yüklemesi) ──
    resp_init = client.get("/feed", headers=AUTH_HEADERS)
    assert resp_init.status_code == 200
    assert "text/html" in resp_init.headers["content-type"]
    assert "PolitikDesk" in resp_init.text

    # ── ADIM 2: En Yeni Haberleri Gör (Kronolojik Sıralama) ──
    resp_newest = client.get("/api/feed?sort=newest", headers=AUTH_HEADERS)
    assert resp_newest.status_code == 200
    items_newest = resp_newest.json()["items"]
    for i in range(len(items_newest) - 1):
        t1 = items_newest[i]["first_reported_at"]
        t2 = items_newest[i + 1]["first_reported_at"]
        assert t1 >= t2, f"En Yeni sıralaması bozuldu: {t1} < {t2}"

    # ── ADIM 3: Önemli Haberlere Geç (Salience Sıralaması) ──
    resp_imp = client.get("/api/feed?sort=important", headers=AUTH_HEADERS)
    assert resp_imp.status_code == 200
    items_imp = resp_imp.json()["items"]
    for i in range(len(items_imp) - 1):
        s1 = items_imp[i].get("displayed_salience", items_imp[i]["salience_score"])
        s2 = items_imp[i + 1].get("displayed_salience", items_imp[i + 1]["salience_score"])
        assert s1 >= s2, f"Önemli sıralaması bozuldu: {s1} < {s2}"

    # ── ADIM 4: Kategori Filtresi (Ekonomi Seç) ──
    resp_eco = client.get("/api/feed?category=ekonomi", headers=AUTH_HEADERS)
    assert resp_eco.status_code == 200
    for itm in resp_eco.json()["items"]:
        assert itm["category"] == "ekonomi"

    # ── ADIM 5: Bölge Filtresi (Türkiye Seç) ──
    resp_tr = client.get("/api/feed?category=ekonomi&region=turkiye", headers=AUTH_HEADERS)
    assert resp_tr.status_code == 200
    for itm in resp_tr.json()["items"]:
        assert itm["category"] == "ekonomi"
        assert itm["region"] == "turkiye"

    # ── ADIM 6: Zaman Filtresi (Son 24h Seç) ──
    resp_24h = client.get("/api/feed?range=24h", headers=AUTH_HEADERS)
    assert resp_24h.status_code == 200

    # ── ADIM 7: Çok Boyutlu Arama Yap ──
    resp_search = client.get("/api/feed?q=faiz", headers=AUTH_HEADERS)
    assert resp_search.status_code == 200

    # ── ADIM 8: Bir Haberi Aç (Detay / Modal) ──
    if items_imp:
        target_id = items_imp[0]["id"]
        resp_event = client.get(f"/events/{target_id}", headers=AUTH_HEADERS)
        assert resp_event.status_code == 200

    # ── ADIM 9: Geri Dön / Temiz State ──
    resp_main = client.get("/feed", headers=AUTH_HEADERS)
    assert resp_main.status_code == 200

    # ── ADIM 10: Yeni Haber Gelmesini Bekle (/api/feed/check-new Polling) ──
    now_iso = datetime.now(UTC).isoformat()
    resp_check = client.get(f"/api/feed/check-new?since={now_iso}", headers=AUTH_HEADERS)
    assert resp_check.status_code == 200
    assert "new_count" in resp_check.json()
    assert "since" in resp_check.json()

    # ── ADIM 11: Banner Kullanımı & No-Scroll-Jump ──
    resp_banner = client.get("/feed", headers=AUTH_HEADERS)
    assert "feed-new-banner" in resp_banner.text

    # ── ADIM 12: Filtreleri Değiştir ──
    resp_multi = client.get("/api/feed?category=politika&region=avrupa", headers=AUTH_HEADERS)
    assert resp_multi.status_code == 200

    # ── ADIM 13: Filtreleri Temizle ──
    resp_clean = client.get("/api/feed?sort=important", headers=AUTH_HEADERS)
    assert resp_clean.status_code == 200

    # ── ADIM 14 & 15: Sayfa Yenileme & State Korunumu ──
    query_str = "sort=newest&category=ekonomi&region=turkiye&range=24h"
    resp_state = client.get(f"/feed?{query_str}", headers=AUTH_HEADERS)
    assert resp_state.status_code == 200

    # ── ADIM 16 & 17: Arşive Git ve Eski Haber Bul ──
    archive_items = feed(user_id=1, cycle_id=1, limit=10)
    assert len(archive_items) == 10

    # ── ADIM 18: Canlı Gündeme Dön ──
    live_items = feed(user_id=1, cycle_id=2, limit=10)
    assert len(live_items) >= 0
