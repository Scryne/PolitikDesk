"""Faz 22: Gündem V2 Çok Boyutlu Filtreleme ve Kombinasyon Doğrulama Testleri."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.db import fetch_one
from politikdesk.web import repository

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer pd_sec_token_9876543210abcdef12345678"}


@pytest.fixture
def sample_events_matrix(db_conn):
    """Farklı kategori, bölge, zaman, kaynak ve durum kombinasyonlarına sahip test olayları matrisi."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM publication_cycles WHERE status = 'active';")
        active_id = int(fetch_one(cur)["id"])
        cur.execute("SELECT id FROM sources WHERE is_active LIMIT 2;")
        sources = [int(r["id"]) for r in cur.fetchall()]
        src1, src2 = sources[0], sources[1]

        # 4 Olay Oluştur:
        # E1: ekonomi, turkiye, 10 dk önce (15m range), src1, ready
        # E2: dis_politika, abd, 2 saat önce (6h range), src2, review
        # E3: guvenlik, orta_dogu, 12 saat önce (24h range), src1, settled
        # E4: teknoloji, asya_pasifik, 3 gün önce (7d range), src2, developing
        cur.execute(
            """
            INSERT INTO events (title, summary, vertical, category, region, salience_score, first_reported_at, last_update_at, cycle_id, review_flag, status, article_count)
            VALUES
              ('TCMB Enflasyon Zirvesi', 'Ekonomi Türkiye', 'macro_economy', 'ekonomi', 'turkiye', 75, now() - interval '10 minutes', now() - interval '10 minutes', %s, NULL, 'developing', 2),
              ('ABD Dışişleri Zirvesi', 'Dış Politika ABD', 'macro_economy', 'dis_politika', 'abd', 60, now() - interval '2 hours', now() - interval '2 hours', %s, 'needs_review', 'developing', 1),
              ('Orta Doğu Güvenlik Hattı', 'Güvenlik Orta Doğu', 'macro_economy', 'guvenlik', 'orta_dogu', 80, now() - interval '12 hours', now() - interval '12 hours', %s, NULL, 'settled', 3),
              ('Asya Pasifik Çip Yatırımı', 'Teknoloji Asya', 'macro_economy', 'teknoloji', 'asya_pasifik', 40, now() - interval '3 days', now() - interval '3 days', %s, NULL, 'developing', 1)
            RETURNING id;
            """,
            (active_id, active_id, active_id, active_id),
        )
        eids = [r["id"] for r in cur.fetchall()]
        e1, e2, e3, e4 = eids[0], eids[1], eids[2], eids[3]

        # Makaleleri ve iddiaları bağla
        cur.execute(
            """
            INSERT INTO articles (source_id, canonical_url, title, excerpt, content_hash, simhash, lang, raw_purge_at, event_id, cycle_id)
            VALUES
              (%s, 'https://test.politikdesk.com/art-e1', 'TCMB Makale', 'TCMB Özet', 'hash_e1', 111, 'tr', now() + interval '7 days', %s, %s),
              (%s, 'https://test.politikdesk.com/art-e2', 'ABD Makale', 'ABD Özet', 'hash_e2', 222, 'tr', now() + interval '7 days', %s, %s),
              (%s, 'https://test.politikdesk.com/art-e3', 'Güvenlik Makale', 'Güvenlik Özet', 'hash_e3', 333, 'tr', now() + interval '7 days', %s, %s),
              (%s, 'https://test.politikdesk.com/art-e4', 'Asya Makale', 'Asya Özet', 'hash_e4', 444, 'tr', now() + interval '7 days', %s, %s);
            """,
            (src1, e1, active_id, src2, e2, active_id, src1, e3, active_id, src2, e4, active_id),
        )

        # İddia ve Kanıt ekle (E1 için ready durumu)
        cur.execute(
            """
            INSERT INTO claims (event_id, claim_text, claim_type, evidence_status, status_reason)
            VALUES (%s, 'TCMB politika faizini değerlendirdi', 'fact', 'strongly_corroborated', '{}'::jsonb)
            RETURNING id;
            """,
            (e1,),
        )
        c1_id = int(fetch_one(cur)["id"])
        cur.execute(
            """
            INSERT INTO evidence (claim_id, article_id, stance, quote_span, extracted_by, confidence)
            VALUES (%s, (SELECT id FROM articles WHERE event_id = %s LIMIT 1), 'supports', 'TCMB resmi açıklaması', 'rules', 0.95);
            """,
            (c1_id, e1),
        )

    yield {"e1": e1, "e2": e2, "e3": e3, "e4": e4, "src1": src1, "src2": src2}

    with db_conn.cursor() as cur:
        cur.execute(
            "DELETE FROM evidence WHERE article_id IN (SELECT id FROM articles WHERE event_id = ANY(%s));",
            (eids,),
        )
        cur.execute("DELETE FROM claims WHERE event_id = ANY(%s);", (eids,))
        cur.execute("DELETE FROM articles WHERE event_id = ANY(%s);", (eids,))
        cur.execute("DELETE FROM events WHERE id = ANY(%s);", (eids,))


@pytest.mark.db
def test_category_filters(sample_events_matrix) -> None:
    """Tüm kategorilerin doğru izole edildiğini doğrular."""
    e = sample_events_matrix

    # Ekonomi
    r_eko = repository.feed(user_id=1, category="ekonomi")
    ids_eko = [x["id"] for x in r_eko]
    assert e["e1"] in ids_eko
    assert e["e2"] not in ids_eko

    # Dış Politika
    r_dis = repository.feed(user_id=1, category="dis_politika")
    ids_dis = [x["id"] for x in r_dis]
    assert e["e2"] in ids_dis
    assert e["e1"] not in ids_dis


@pytest.mark.db
def test_region_filters(sample_events_matrix) -> None:
    """Tüm bölgelerin doğru izole edildiğini doğrular."""
    e = sample_events_matrix

    # Türkiye
    r_tr = repository.feed(user_id=1, region="turkiye")
    ids_tr = [x["id"] for x in r_tr]
    assert e["e1"] in ids_tr
    assert e["e2"] not in ids_tr

    # ABD
    r_abd = repository.feed(user_id=1, region="abd")
    ids_abd = [x["id"] for x in r_abd]
    assert e["e2"] in ids_abd
    assert e["e1"] not in ids_abd


@pytest.mark.db
def test_time_range_filters(sample_events_matrix) -> None:
    """Zaman aralığı filtrelerinin doğruluğu (15m, 1h, 6h, 24h, 7d)."""
    e = sample_events_matrix

    # 15 dakika: yalnızca E1 (10 dk önce)
    r_15m = repository.feed(user_id=1, time_range="15m")
    ids_15m = [x["id"] for x in r_15m]
    assert e["e1"] in ids_15m
    assert e["e2"] not in ids_15m
    assert e["e3"] not in ids_15m

    # 6 saat: E1 ve E2 (2 saat önce)
    r_6h = repository.feed(user_id=1, time_range="6h")
    ids_6h = [x["id"] for x in r_6h]
    assert e["e1"] in ids_6h
    assert e["e2"] in ids_6h
    assert e["e3"] not in ids_6h

    # 24 saat: E1, E2, E3
    r_24h = repository.feed(user_id=1, time_range="24h")
    ids_24h = [x["id"] for x in r_24h]
    assert e["e1"] in ids_24h
    assert e["e2"] in ids_24h
    assert e["e3"] in ids_24h
    assert e["e4"] not in ids_24h


@pytest.mark.db
def test_source_filters(sample_events_matrix) -> None:
    """Belirli bir kaynağa göre filtreleme."""
    e = sample_events_matrix

    r_src1 = repository.feed(user_id=1, source_id=e["src1"])
    ids_src1 = [x["id"] for x in r_src1]
    assert e["e1"] in ids_src1
    assert e["e3"] in ids_src1
    assert e["e2"] not in ids_src1


@pytest.mark.db
def test_composite_multi_filters_api(sample_events_matrix) -> None:
    """Kategori + Bölge + Zaman + Sıralama çoklu filtrelerinin HTTP API üzerinden doğrulanması."""
    e = sample_events_matrix

    resp = client.get(
        "/api/feed?sort=newest&category=ekonomi&region=turkiye&time_range=15m",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = [x["id"] for x in data["items"]]

    assert e["e1"] in item_ids
    assert e["e2"] not in item_ids
    assert e["e3"] not in item_ids
    assert e["e4"] not in item_ids
