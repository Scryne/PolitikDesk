"""Faz 23: Gündem V3 Production UX, Sıralama, Keşif ve Filtre Denetim Testleri."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from politikdesk.analysis.taxonomy import CATEGORIES, REGIONS
from politikdesk.api.main import app
from politikdesk.db import fetch_one
from politikdesk.web import repository
from politikdesk.web.feed import SORT_MODES, _active_filters_tray, _build_feed_url, _discovery_bar

client = TestClient(app)
AUTH_HEADERS = {"X-User-Id": "1"}


def test_build_feed_url_helper() -> None:
    """_build_feed_url fonksiyonunun temiz ve doğru URL ürettiğini doğrular."""
    # Varsayılanlar temizlenmeli
    assert _build_feed_url() == "/feed"

    # Sıralama ve filtreler eklenmeli
    url = _build_feed_url(sort="newest", category="ekonomi", region="turkiye", range_="24h")
    assert "sort=newest" in url
    assert "category=ekonomi" in url
    assert "region=turkiye" in url
    assert "range=24h" in url

    # Default sort keep_default_sort=True ile zorlanabilmeli
    url_def = _build_feed_url(sort="important", keep_default_sort=True)
    assert url_def == "/feed?sort=important"


def test_active_filters_tray_rendering() -> None:
    """Aktif filtre tepsisinin (tray) seçili filtrelere göre doğru çipleri bastığını doğrular."""
    # Hiçbir filtre yokken boş string dönmeli
    tray_empty = _active_filters_tray(
        selected_sort="important",
        selected_f="all",
        selected_cat="all",
        selected_reg="all",
        selected_range="all",
        source=None,
        sources_list=[],
        q=None,
    )
    assert tray_empty == ""

    # Kategori ve Bölge aktifken çipleri ve silme bağlantılarını içermeli
    tray_active = _active_filters_tray(
        selected_sort="newest",
        selected_f="ready",
        selected_cat="ekonomi",
        selected_reg="turkiye",
        selected_range="24h",
        source=None,
        sources_list=[],
        q="enflasyon",
    )
    assert "feed-active-tray" in tray_active
    assert "Kategori:" in tray_active
    assert "Ekonomi &amp; Finans" in tray_active or "Ekonomi" in tray_active
    assert "Bölge:" in tray_active
    assert "Türkiye" in tray_active
    assert "Zaman:" in tray_active
    assert "Son 24 saat" in tray_active
    assert "Arama:" in tray_active
    assert "enflasyon" in tray_active
    assert "Durum:" in tray_active
    assert "Yazıma hazır" in tray_active
    assert "Filtreleri Temizle" in tray_active


def test_discovery_bar_rendering() -> None:
    """Keşif çubuğunun (Discovery Bar) tüm kategori ve bölge çiplerini sunduğunu doğrular."""
    disc_html = _discovery_bar(
        selected_sort="important",
        selected_f="all",
        selected_cat="ekonomi",
        selected_reg="turkiye",
        selected_range="all",
        source=None,
        q=None,
    )
    assert "feed-discovery-bar" in disc_html
    assert "Kategori" in disc_html
    assert "Bölge" in disc_html
    assert "feed-chip" in disc_html

    # Tüm 10 kategori ve 7 bölge olmalı
    for k, _lbl in CATEGORIES:
        assert f"category={k}" in disc_html or k == "all"
    for r, _lbl in REGIONS:
        assert f"region={r}" in disc_html or r == "all"


@pytest.mark.db
def test_gundem_v3_page_html_and_tagline(db_conn) -> None:
    """Gündem sayfasının sıralama modları, açıklayıcı tagline ve keşif bileşenlerini içerdiğini doğrular."""
    resp = client.get("/feed?sort=important", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    html = resp.text

    assert "feed-toolbar" in html
    assert "feed-mode-tagline" in html
    assert "Editoryal önem ve etki sıralaması" in html
    assert "feed-discovery-bar" in html
    assert "feed-chip" in html
    assert "feed-new-banner" in html

    # Sıralama modlarının tamamı mevcut olmalı
    for sort_key, sort_lbl, _icon, _desc in SORT_MODES:
        assert f"sort={sort_key}" in html
        assert sort_lbl in html


@pytest.mark.db
def test_gundem_v3_active_filter_tray_e2e(db_conn) -> None:
    """Filtre seçildiğinde aktif filtre tepsisinin HTML içinde çıktığını doğrular."""
    resp = client.get(
        "/feed?category=guvenlik&region=orta_dogu&range=6h&f=ready&q=harekat",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    html = resp.text

    assert "feed-active-tray" in html
    assert "Güvenlik &amp; Savunma" in html or "Güvenlik" in html
    assert "Orta Doğu" in html
    assert "Son 6 saat" in html
    assert "Yazıma hazır" in html
    assert "harekat" in html
    assert "Filtreleri Temizle" in html


@pytest.mark.db
def test_gundem_v3_sort_modes_execution(db_conn) -> None:
    """Sıralama modlarının veritabanı üzerinde doğru çalıştığını doğrular."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM publication_cycles WHERE status = 'active';")
        active_id = int(fetch_one(cur)["id"])

        cur.execute(
            """
            INSERT INTO events (title, vertical, salience_score, first_reported_at, last_update_at, cycle_id)
            VALUES
              ('V3 Düşük Salience Çok Yeni', 'macro_economy', 15, now() - interval '1 minute', now() - interval '1 minute', %s),
              ('V3 Yüksek Salience Eski', 'macro_economy', 90, now() - interval '20 minutes', now() - interval '20 minutes', %s),
              ('V3 Orta Salience Yeni Güncellenen', 'macro_economy', 45, now() - interval '10 minutes', now(), %s)
            RETURNING id;
            """,
            (active_id, active_id, active_id),
        )
        created_ids = [r["id"] for r in cur.fetchall()]

    try:
        feed_imp = repository.feed(user_id=1, sort="important", limit=500)
        found_imp = [r for r in feed_imp if r["id"] in created_ids]
        assert len(found_imp) >= 2
        assert found_imp[0]["salience_score"] >= found_imp[1]["salience_score"]

        feed_new = repository.feed(user_id=1, sort="newest", limit=500)
        found_new = [r for r in feed_new if r["id"] in created_ids]
        assert len(found_new) >= 2
        assert (found_new[0].get("first_reported_at") or found_new[0]["created_at"]) >= (
            found_new[1].get("first_reported_at") or found_new[1]["created_at"]
        )

        feed_upd = repository.feed(user_id=1, sort="updated", limit=500)
        found_upd = [r for r in feed_upd if r["id"] in created_ids]
        assert len(found_upd) >= 2
        assert found_upd[0]["last_update_at"] >= found_upd[1]["last_update_at"]
    finally:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE id = ANY(%s)", (created_ids,))
            db_conn.commit()
