"""Faz 22: Gündem V2 Sıralama Modları (Önemli, En Yeni, Son Güncellenen) Derinlik Testleri."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.db import fetch_one
from politikdesk.web import repository

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer pd_sec_token_9876543210abcdef12345678"}


@pytest.fixture
def sorting_scenario_events(db_conn):
    """
    Sıralama Çatışması Senaryosu (Adversarial Divergence):
      A — 2 saat önce ilk bildirim, son güncelleme 10 dk önce, salience 85 (Önemli + Güncellenen zirvesi)
      B — 5 dakika önce ilk bildirim, son güncelleme 5 dk önce, salience 20 (En Yeni 2. sıra, önemsiz)
      C — 1 dakika önce ilk bildirim, son güncelleme 1 dk önce, salience 5 (En Yeni 1. sıra, çok önemsiz)
    """
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM publication_cycles WHERE status = 'active';")
        active_id = int(fetch_one(cur)["id"])

        cur.execute(
            """
            INSERT INTO events (title, summary, vertical, category, region, salience_score, first_reported_at, last_update_at, cycle_id)
            VALUES
              ('Olay A — Yüksek Önemli Eski', 'Özet A', 'macro_economy', 'ekonomi', 'turkiye', 85, now() - interval '2 hours', now() - interval '10 minutes', %s),
              ('Olay B — Orta Yeni Düşük Önem', 'Özet B', 'macro_economy', 'politika', 'turkiye', 20, now() - interval '5 minutes', now() - interval '5 minutes', %s),
              ('Olay C — En Yeni Önemsiz', 'Özet C', 'macro_economy', 'teknoloji', 'turkiye', 5, now() - interval '1 minute', now() - interval '1 minute', %s)
            RETURNING id, title;
            """,
            (active_id, active_id, active_id),
        )
        rows = cur.fetchall()
        id_map = {r["title"]: r["id"] for r in rows}

    yield id_map

    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM events WHERE id = ANY(%s);", (list(id_map.values()),))


@pytest.mark.db
def test_newest_sort_is_strictly_chronological(sorting_scenario_events) -> None:
    """'newest' modunda sıralamanın kesin olarak C -> B -> A olduğunu doğrular."""
    ids = sorting_scenario_events

    rows = repository.feed(user_id=1, sort="newest", limit=500)
    event_ids = [r["id"] for r in rows if r["id"] in ids.values()]

    assert event_ids == [
        ids["Olay C — En Yeni Önemsiz"],
        ids["Olay B — Orta Yeni Düşük Önem"],
        ids["Olay A — Yüksek Önemli Eski"],
    ], f"En Yeni sıralaması kronolojik sırayı vermedi! Sıralama: {event_ids}"


@pytest.mark.db
def test_important_sort_is_salience_dominated(sorting_scenario_events) -> None:
    """'important' modunda sıralamanın önem puanına göre A (85) -> B (20) -> C (5) olduğunu doğrular."""
    ids = sorting_scenario_events

    rows = repository.feed(user_id=1, sort="important", limit=500)
    event_ids = [r["id"] for r in rows if r["id"] in ids.values()]

    assert event_ids == [
        ids["Olay A — Yüksek Önemli Eski"],
        ids["Olay B — Orta Yeni Düşük Önem"],
        ids["Olay C — En Yeni Önemsiz"],
    ], f"Önemli sıralaması salience sırasını vermedi! Sıralama: {event_ids}"


@pytest.mark.db
def test_updated_sort_is_last_update_dominated(sorting_scenario_events) -> None:
    """'updated' modunda son güncelleme zamanına göre C (1 dk) -> B (5 dk) -> A (10 dk) olduğunu doğrular."""
    ids = sorting_scenario_events

    rows = repository.feed(user_id=1, sort="updated", limit=500)
    event_ids = [r["id"] for r in rows if r["id"] in ids.values()]

    assert event_ids == [
        ids["Olay C — En Yeni Önemsiz"],
        ids["Olay B — Orta Yeni Düşük Önem"],
        ids["Olay A — Yüksek Önemli Eski"],
    ], f"Son Güncellenen sıralaması zaman sırasını vermedi! Sıralama: {event_ids}"


@pytest.mark.db
def test_sorting_api_contract(sorting_scenario_events) -> None:
    """HTTP API üzerinde sıralama parametrelerinin doğruluğunu doğrular."""
    ids = sorting_scenario_events

    # /api/feed?sort=newest
    r_new = client.get("/api/feed?sort=newest", headers=AUTH_HEADERS).json()
    new_ids = [x["id"] for x in r_new["items"] if x["id"] in ids.values()]
    assert new_ids[0] == ids["Olay C — En Yeni Önemsiz"]

    # /api/feed?sort=important
    r_imp = client.get("/api/feed?sort=important", headers=AUTH_HEADERS).json()
    imp_ids = [x["id"] for x in r_imp["items"] if x["id"] in ids.values()]
    assert imp_ids[0] == ids["Olay A — Yüksek Önemli Eski"]
