"""Faz 2 İş Kolu D — bağlam ve takvim (F2-17, F2-18, F2-19).

Veritabanı gerektirir: her iki bileşenin de sözleşmesi kalıcı ilişkilerin
doğru kurulmasıdır.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from politikdesk.context.related import find_related, link_related
from politikdesk.context.scheduler_match import add_scheduled, match_pending

pytestmark = pytest.mark.db

SLUG = "pytest-context-src"
DIM = 1024


def _vec(seed: float) -> str:
    return "[" + ",".join(f"{seed:.6f}" for _ in range(DIM)) + "]"


@pytest.fixture()
def fixtures(db_conn):  # noqa: ANN001, ANN201
    """İki ilişkili olay (aynı seri, farklı ay) + bir alakasız olay."""
    now = datetime.now(UTC)
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sources (name, slug, tier, kind, access_method, tos_status)
            VALUES ('Pytest Context', %s, 1, 'official', 'official_feed', 'allowed')
            ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name RETURNING id
            """,
            (SLUG,),
        )
        source_id = cur.fetchone()["id"]

        # İki olay birbirine çok yakın (aynı seri), üçüncü uzak.
        specs = [
            ("pytest enflasyon haziran", 0.30, now - timedelta(days=60)),
            ("pytest enflasyon temmuz", 0.3001, now - timedelta(days=30)),
            ("pytest alakasiz olay", -0.9, now - timedelta(days=45)),
        ]
        event_ids = []
        for title, seed, at in specs:
            cur.execute(
                """
                INSERT INTO events (title, vertical, centroid_embedding,
                                    first_reported_at, last_update_at, article_count)
                VALUES (%s, 'macro_economy', %s::vector, %s, %s, 1)
                RETURNING id
                """,
                (title, _vec(seed), at, at),
            )
            event_ids.append(cur.fetchone()["id"])
    db_conn.commit()

    yield {"events": event_ids, "source_id": source_id, "now": now}

    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM event_relations WHERE from_event_id = ANY(%s) "
                    "OR to_event_id = ANY(%s)", (event_ids, event_ids))
        cur.execute("DELETE FROM scheduled_events WHERE source_id = %s", (source_id,))
        cur.execute("DELETE FROM audit_log WHERE target = ANY(%s)",
                    ([f"events/{e}" for e in event_ids],))
        cur.execute("DELETE FROM articles WHERE source_id = %s", (source_id,))
        cur.execute("DELETE FROM events WHERE id = ANY(%s)", (event_ids,))
        cur.execute("DELETE FROM sources WHERE id = %s", (source_id,))
    db_conn.commit()


# ==========================================================================
# F2-17 — tarihsel bağlam
# ==========================================================================
def test_similar_past_event_is_found(db_conn, fixtures) -> None:  # noqa: ANN001
    """DoD: bir enflasyon olayı, önceki ayın enflasyon olayına bağlanıyor."""
    older, newer, _unrelated = fixtures["events"]
    related = find_related(newer)
    assert older in [r.event_id for r in related]


def test_unrelated_event_is_not_linked(db_conn, fixtures) -> None:  # noqa: ANN001
    _older, newer, unrelated = fixtures["events"]
    assert unrelated not in [r.event_id for r in find_related(newer)]


def test_context_only_looks_backwards(db_conn, fixtures) -> None:  # noqa: ANN001
    """Tarihsel bağlam geriye bakar; ileriye bakan bağ diğer uçtan kurulur."""
    older, newer, _ = fixtures["events"]
    assert newer not in [r.event_id for r in find_related(older)]


def test_link_related_writes_same_thread_relation(db_conn, fixtures) -> None:  # noqa: ANN001
    older, newer, _ = fixtures["events"]
    assert link_related(newer) >= 1
    db_conn.commit()

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT relation, similarity FROM event_relations "
            "WHERE from_event_id = %s AND to_event_id = %s",
            (newer, older),
        )
        row = cur.fetchone()
    db_conn.commit()

    assert row is not None
    assert row["relation"] == "same_thread"
    assert row["similarity"] > 0.8


def test_linking_is_idempotent(db_conn, fixtures) -> None:  # noqa: ANN001
    """İkinci koşum yeni satır üretmemeli — beat tekrar tekrar koşar."""
    _older, newer, _ = fixtures["events"]
    link_related(newer)
    link_related(newer)
    db_conn.commit()

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM event_relations WHERE from_event_id = %s",
            (newer,),
        )
        assert cur.fetchone()["n"] == 1
    db_conn.commit()


# ==========================================================================
# F2-18 / F2-19 — takvim ve eşleştirme
# ==========================================================================
def test_scheduled_event_matches_the_event_at_that_time(db_conn, fixtures) -> None:  # noqa: ANN001
    """F2-19 DoD: takvimdeki kayıt, o saatte gelen olayı otomatik alır."""
    _older, newer, _ = fixtures["events"]
    with db_conn.cursor() as cur:
        cur.execute("SELECT first_reported_at FROM events WHERE id = %s", (newer,))
        expected_at = cur.fetchone()["first_reported_at"]
        # Olayın kaynak koşulunu sağlaması için bir makale gerekir.
        cur.execute(
            """
            INSERT INTO articles (source_id, canonical_url, title, content_hash, event_id)
            VALUES (%s, 'https://pytest.test/ctx/1', 'pytest makale', 'h-ctx-1', %s)
            """,
            (fixtures["source_id"], newer),
        )
    db_conn.commit()

    scheduled_id = add_scheduled(
        title="pytest beklenen enflasyon verisi",
        expected_at=expected_at + timedelta(minutes=20),
        source_slug=SLUG,
    )
    match_pending()

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT linked_event_id, status FROM scheduled_events WHERE id = %s",
            (scheduled_id,),
        )
        row = cur.fetchone()
    db_conn.commit()

    assert row["linked_event_id"] == newer
    assert row["status"] == "occurred"


def test_event_from_another_source_is_not_matched(db_conn, fixtures) -> None:  # noqa: ANN001
    """Yalnız zamana bakan eşleştirme, o saatteki alakasız haberi bağlardı."""
    _older, newer, _ = fixtures["events"]
    with db_conn.cursor() as cur:
        cur.execute("SELECT first_reported_at FROM events WHERE id = %s", (newer,))
        expected_at = cur.fetchone()["first_reported_at"]
        cur.execute("SELECT id FROM sources WHERE slug = 'tcmb'")
        other = cur.fetchone()
    db_conn.commit()
    if other is None:
        pytest.skip("tcmb kaynağı yok — kaynak ayrımı testi atlandı")

    scheduled_id = add_scheduled(
        title="pytest baska kaynagin beklenen verisi",
        expected_at=expected_at,
        source_slug="tcmb",
    )
    match_pending()

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT linked_event_id FROM scheduled_events WHERE id = %s", (scheduled_id,)
        )
        linked = cur.fetchone()["linked_event_id"]
        cur.execute("DELETE FROM scheduled_events WHERE id = %s", (scheduled_id,))
    db_conn.commit()

    assert linked != newer


def test_unknown_source_slug_is_rejected(db_conn) -> None:  # noqa: ANN001
    with pytest.raises(ValueError, match="Kaynak bulunamadı"):
        add_scheduled(title="pytest", expected_at=datetime.now(UTC), source_slug="yok-boyle")
