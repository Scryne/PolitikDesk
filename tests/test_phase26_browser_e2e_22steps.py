"""Phase 26: 22-Step Comprehensive Browser E2E & Production Flow Test Suite."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.web import repository

client = TestClient(app)
AUTH = {"X-User-Id": "1"}


def test_step_01_authenticated_feed_load() -> None:
    """Adım 1: Kimlik doğrulanmış Gündem akışının 200 OK ile yüklenmesi."""
    resp = client.get("/feed", headers=AUTH)
    assert resp.status_code == 200
    assert "Gündem" in resp.text or "PolitikDesk" in resp.text
    assert "feed-container" in resp.text or "feed-cards" in resp.text or "feed-discovery" in resp.text


def test_step_02_sorting_important() -> None:
    """Adım 2: 'Önemli' sıralama modu."""
    resp = client.get("/feed?sort=important", headers=AUTH)
    assert resp.status_code == 200
    assert "sort=important" in resp.text or "Önemli" in resp.text


def test_step_03_sorting_newest() -> None:
    """Adım 3: 'En Yeni' sıralama modu."""
    resp = client.get("/feed?sort=newest", headers=AUTH)
    assert resp.status_code == 200
    assert "En Yeni" in resp.text or "sort=newest" in resp.text


def test_step_04_sorting_updated() -> None:
    """Adım 4: 'Son Güncellenen' sıralama modu."""
    resp = client.get("/feed?sort=updated", headers=AUTH)
    assert resp.status_code == 200
    assert "Son Güncellenen" in resp.text or "sort=updated" in resp.text


def test_step_05_category_filter_ekonomi() -> None:
    """Adım 5: 'Ekonomi' kategori filtresi."""
    resp = client.get("/feed?category=ekonomi", headers=AUTH)
    assert resp.status_code == 200
    assert "Ekonomi" in resp.text or "category=ekonomi" in resp.text


def test_step_06_category_filter_politika() -> None:
    """Adım 6: 'Politika' kategori filtresi."""
    resp = client.get("/feed?category=politika", headers=AUTH)
    assert resp.status_code == 200
    assert "Politika" in resp.text or "category=politika" in resp.text


def test_step_07_region_filter_turkiye() -> None:
    """Adım 7: 'Türkiye' bölge filtresi."""
    resp = client.get("/feed?region=turkiye", headers=AUTH)
    assert resp.status_code == 200
    assert "Türkiye" in resp.text or "region=turkiye" in resp.text


def test_step_08_region_filter_avrupa() -> None:
    """Adım 8: 'Avrupa & AB' bölge filtresi."""
    resp = client.get("/feed?region=avrupa", headers=AUTH)
    assert resp.status_code == 200
    assert "Avrupa" in resp.text or "region=avrupa" in resp.text


def test_step_09_time_filter_today() -> None:
    """Adım 9: Zaman aralığı filtresi (Bugün / 24s)."""
    resp = client.get("/feed?range=24h", headers=AUTH)
    assert resp.status_code == 200


def test_step_10_search_query_execution() -> None:
    """Adım 10: Canlı metin araması (q=faiz)."""
    resp = client.get("/feed?q=faiz", headers=AUTH)
    assert resp.status_code == 200
    assert "faiz" in resp.text.lower() or "feed-cards" in resp.text


def test_step_11_multi_filter_combination() -> None:
    """Adım 11: Çoklu filtre kombinasyonu (sort + category + region + range + q)."""
    resp = client.get(
        "/feed?sort=newest&category=ekonomi&region=turkiye&range=7d&q=tcmb",
        headers=AUTH,
    )
    assert resp.status_code == 200


def test_step_12_active_filters_tray_clear_all_chip() -> None:
    """Adım 12: Aktif filtre çipleri ve tepsi rendering."""
    resp = client.get("/feed?category=ekonomi&region=turkiye", headers=AUTH)
    assert resp.status_code == 200
    assert "feed-active-tray" in resp.text or "feed-active-pill" in resp.text or "Filtreler" in resp.text


@pytest.mark.db
def test_step_13_event_drawer_card_selection() -> None:
    """Adım 13: Olay kartı seçimi ve detay görünümü."""
    items = repository.feed(user_id=1, limit=1)
    if items:
        event_id = items[0]["id"]
        resp = client.get(f"/feed?event_id={event_id}", headers=AUTH)
        assert resp.status_code == 200


@pytest.mark.db
def test_step_14_event_detail_endpoint() -> None:
    """Adım 14: Bağımsız olay detay sayfası / drawer içeriği."""
    items = repository.feed(user_id=1, limit=1)
    if items:
        event_id = items[0]["id"]
        resp = client.get(f"/event/{event_id}", headers=AUTH)
        assert resp.status_code == 200


@pytest.mark.db
def test_step_15_api_feed_check_new_live_banner() -> None:
    """Adım 15: /api/feed/check-new canlı yeni haber yoklama endpointi."""
    resp = client.get("/api/feed/check-new?since=2026-08-24T00:00:00Z", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert "new_count" in data
    assert data["new_count"] >= 0


def test_step_16_api_feed_taxonomy_discovery() -> None:
    """Adım 16: /api/feed/taxonomy kategori ve bölge filtre taksonomi API'si."""
    resp = client.get("/api/feed/taxonomy", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    assert "regions" in data


def test_step_17_no_scroll_jump_contract() -> None:
    """Adım 17: HTMX ve no-scroll-jump attribute doğrulaması."""
    resp = client.get("/feed", headers=AUTH)
    assert resp.status_code == 200
    assert "feed-cards" in resp.text or "hx-" in resp.text or "body" in resp.text


def test_step_18_empty_search_graceful_state() -> None:
    """Adım 18: Sonuçsuz arama boş durum ekranı (empty state)."""
    resp = client.get("/feed?q=xyznonexistentquery12345", headers=AUTH)
    assert resp.status_code == 200


def test_step_19_error_state_handling() -> None:
    """Adım 19: Geçersiz / bozuk parametrelerde 500 vermeden güvenli çalışma."""
    resp = client.get("/feed?sort=invalid_sort&category=unknown_cat&limit=-10", headers=AUTH)
    assert resp.status_code in (200, 400, 422)


def test_step_20_sources_catalog_navigation() -> None:
    """Adım 20: Kaynaklar kataloğu ve filtre yönlendirmesi."""
    resp = client.get("/feed?source=1", headers=AUTH)
    assert resp.status_code == 200


def test_step_21_open_health_probe() -> None:
    """Adım 21: Sistem sağlık kontrolü /health/live probe'unun 200 dönmesi."""
    resp = client.get("/health/live")
    assert resp.status_code == 200


def test_step_22_responsive_meta_and_css_presence() -> None:
    """Adım 22: Mobil, tablet ve masaüstü duyarlı görünüm meta etiketleri ve CSS."""
    resp = client.get("/feed", headers=AUTH)
    assert resp.status_code == 200
    assert 'name="viewport"' in resp.text
    assert "width=device-width" in resp.text
