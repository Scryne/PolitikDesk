"""Faz 23: 10 Gerçek Gazeteci Persona Senaryosu E2E Test Süiti."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.db import fetch_one

client = TestClient(app)
AUTH_HEADERS = {"X-User-Id": "1"}


@pytest.fixture
def sample_editorial_events(db_conn) -> list[int]:
    """Testler için zengin editoryal olay kümesi oluşturur."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM publication_cycles WHERE status = 'active';")
        active_id = int(fetch_one(cur)["id"])

        now = datetime.now(UTC)

        # 1. 10 dakika önce Türkiye haberi
        # 2. 2 saat önce Ekonomi/Finans yüksek önem haberi
        # 3. 5 saat önce Orta Doğu güncellenen haberi
        # 4. 12 saat önce Enerji haberi
        # 5. 20 saat önce Güvenlik haberi
        cur.execute(
            """
            INSERT INTO events (title, vertical, category, region, salience_score, first_reported_at, last_update_at, cycle_id)
            VALUES
              ('Son Dakika: Ankara Deprem Dairesi Açıklaması', 'politics', 'politika', 'turkiye', 60, %s, %s, %s),
              ('TCMB Enflasyon Raporu ve Faiz Kararı Özeti', 'macro_economy', 'ekonomi', 'turkiye', 88, %s, %s, %s),
              ('Orta Doğu Ateşkes Zirvesi ve Diplomatik Müzakere', 'diplomacy', 'dis_politika', 'orta_dogu', 80, %s, %s, %s),
              ('BOTAŞ ve Karadeniz Gazı Yeni Üretim Fazı', 'energy', 'enerji', 'turkiye', 70, %s, %s, %s),
              ('Milli Savunma Bakanlığı Sınır Güvenliği Raporu', 'security', 'guvenlik', 'turkiye', 65, %s, %s, %s)
            RETURNING id;
            """,
            (
                now - timedelta(minutes=10),
                now - timedelta(minutes=10),
                active_id,
                now - timedelta(hours=2),
                now - timedelta(hours=2),
                active_id,
                now - timedelta(hours=5),
                now - timedelta(minutes=5),
                active_id,
                now - timedelta(hours=12),
                now - timedelta(hours=12),
                active_id,
                now - timedelta(hours=20),
                now - timedelta(hours=20),
                active_id,
            ),
        )
        created_ids = [r["id"] for r in cur.fetchall()]

    yield created_ids

    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM events WHERE id = ANY(%s)", (created_ids,))
        db_conn.commit()


@pytest.mark.db
def test_scenario_1_breaking_turkey_15m(sample_editorial_events) -> None:
    """Senaryo 1: 'Son 15 dakikada Türkiye'de ne oldu?'"""
    resp = client.get("/feed?range=15m&region=turkiye", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    html = resp.text

    assert "feed-active-tray" in html
    assert "Türkiye" in html
    assert "Son 15 dakika" in html
    # 10 dakika önceki Ankara haberi görünmeli
    assert "Ankara Deprem Dairesi" in html


@pytest.mark.db
def test_scenario_2_important_economy_today(sample_editorial_events) -> None:
    """Senaryo 2: 'Bugünün en önemli ekonomi gelişmelerini göster.'"""
    resp = client.get(
        "/feed?sort=important&category=ekonomi&range=24h",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    html = resp.text

    assert "feed-mode-tagline" in html
    assert "Editoryal önem ve etki sıralaması" in html
    assert "TCMB Enflasyon Raporu" in html


@pytest.mark.db
def test_scenario_3_middle_east_updated_stream(sample_editorial_events) -> None:
    """Senaryo 3: 'Orta Doğu'daki son gelişmeleri bul.'"""
    resp = client.get(
        "/feed?sort=updated&region=orta_dogu",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    html = resp.text

    assert "Son Güncellenen" in html
    assert "Orta Doğu Ateşkes Zirvesi" in html


@pytest.mark.db
def test_scenario_4_energy_last_24h(sample_editorial_events) -> None:
    """Senaryo 4: 'Son 24 saatte enerji alanındaki gelişmeleri göster.'"""
    resp = client.get("/feed?category=enerji&range=24h", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    html = resp.text

    assert "Enerji &amp; İklim" in html or "Enerji" in html
    assert "Karadeniz Gazı" in html


@pytest.mark.db
def test_scenario_5_chronological_newest(sample_editorial_events) -> None:
    """Senaryo 5: 'En yeni haberleri kronolojik olarak göster.'"""
    resp = client.get("/feed?sort=newest", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    html = resp.text

    assert "En Yeni" in html
    assert "Kronolojik Akış" in html


@pytest.mark.db
def test_scenario_6_editorial_salience_mode(sample_editorial_events) -> None:
    """Senaryo 6: 'Şu anda en önemli gelişmeleri göster.'"""
    resp = client.get("/feed?sort=important", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    html = resp.text

    assert "Önemli" in html
    assert "Editoryal önem ve etki sıralaması" in html


@pytest.mark.db
def test_scenario_7_live_new_news_check_and_banner(sample_editorial_events) -> None:
    """Senaryo 7: 'Bir haber geldi. Yeni olduğunu gör ve akışımı bozmadan aç.'"""
    # 1. check-new endpointini çağır
    check_resp = client.get("/api/feed/check-new?since=2020-01-01T00:00:00Z", headers=AUTH_HEADERS)
    assert check_resp.status_code == 200
    data = check_resp.json()
    assert "new_count" in data
    assert data["new_count"] >= 5

    # 2. Sessiz yenileme parça endpointi (/feed/cards)
    cards_resp = client.get("/feed/cards?sort=important", headers=AUTH_HEADERS)
    assert cards_resp.status_code == 200
    cards_html = cards_resp.text
    assert "feed-card" in cards_html or "card" in cards_html


@pytest.mark.db
def test_scenario_8_source_specific_filtering(db_conn) -> None:
    """Senaryo 8: 'Belirli bir kaynaktan gelen haberleri bul.'"""
    resp = client.get("/feed?source=1", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    html = resp.text
    assert "feed-toolbar" in html


@pytest.mark.db
def test_scenario_9_multi_dimensional_discovery(sample_editorial_events) -> None:
    """Senaryo 9: 'Bir haberi kategori + bölge + zaman filtresiyle bul.'"""
    resp = client.get(
        "/feed?category=guvenlik&region=turkiye&range=24h&q=Savunma",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    html = resp.text

    assert "feed-active-tray" in html
    assert "Güvenlik" in html
    assert "Türkiye" in html
    assert "Son 24 saat" in html
    assert "Savunma" in html


@pytest.mark.db
def test_scenario_10_filter_persistence_and_removal(sample_editorial_events) -> None:
    """Senaryo 10: 'Sayfayı yeniledikten sonra tüm filtrelerimi ve sorting tercihlerimi koru; tek tıkla kaldır.'"""
    resp = client.get(
        "/feed?sort=newest&category=ekonomi&region=turkiye&range=24h",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    html = resp.text

    # Aktif haplar olmalı
    assert "Kategori:" in html
    assert "Bölge:" in html
    assert "Zaman:" in html

    # Her birinin kaldırma linki olmalı
    assert 'title="Kategori filtresini kaldır"' in html
    assert 'title="Bölge filtresini kaldır"' in html
    assert 'title="Zaman filtresini kaldır"' in html
    assert 'title="Tüm filtreleri sıfırla"' in html
