"""F2-05 — merge / split kaçış valfleri (G2 koşul 8: %100 geri alınabilir).

Bu testler veritabanı gerektirir: merge/split'in asıl sözleşmesi **kalıcı
durumun** bozulmamasıdır. Saf fonksiyon testi bunu gösteremez.

Her test kendi verisini kurar ve siler; mevcut kayıtlara dokunmaz.
"""

from __future__ import annotations

import pytest

from politikdesk.clustering.centroid import drift, recompute
from politikdesk.clustering.merger import (
    MergeError,
    merge_events,
    resolve_review,
    review_queue,
    split_event,
    undo_merge,
    undo_split,
)

pytestmark = pytest.mark.db

TEST_SLUG = "pytest-merger-src"
DIM = 1024


def _vec(seed: float) -> str:
    return "[" + ",".join(f"{seed + i * 1e-4:.6f}" for i in range(DIM)) + "]"


@pytest.fixture()
def fixtures(db_conn):  # noqa: ANN001, ANN201
    """İki olay ve toplam üç makale kurar; test sonunda hepsini siler."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sources (name, slug, tier, kind, access_method, tos_status)
            VALUES ('Pytest', %s, 1, 'official', 'official_feed', 'allowed')
            ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name RETURNING id
            """,
            (TEST_SLUG,),
        )
        source_id = cur.fetchone()["id"]

        event_ids: list[int] = []
        for n in (1, 2):
            cur.execute(
                """
                INSERT INTO events (title, vertical, centroid_embedding,
                                    first_reported_at, last_update_at, article_count)
                VALUES (%s, 'macro_economy', %s::vector, now(), now(), 0)
                RETURNING id
                """,
                (f"pytest olay {n}", _vec(0.1 * n)),
            )
            event_ids.append(cur.fetchone()["id"])

        article_ids: list[int] = []
        # olay 1'e iki makale, olay 2'ye bir makale
        for i, event_id in enumerate((event_ids[0], event_ids[0], event_ids[1])):
            cur.execute(
                """
                INSERT INTO articles (source_id, canonical_url, title, content_hash,
                                      embedding, event_id, published_at)
                VALUES (%s, %s, %s, %s, %s::vector, %s, now())
                RETURNING id
                """,
                (
                    source_id,
                    f"https://pytest.test/merger/{i}",
                    f"pytest makale {i}",
                    f"hash-merger-{i}",
                    _vec(0.1 * (i + 1)),
                    event_id,
                ),
            )
            article_ids.append(cur.fetchone()["id"])

        # Fikstür TUTARLI olmalı: merkez, üyelerinin ortalamasıdır. Keyfî bir
        # merkez kurulursa ilk merge/split işlemi onu düzeltir ve "geri alma
        # durumu bozdu" gibi görünür — testin kendisi yanlış alarm üretir.
        for event_id in event_ids:
            cur.execute(
                """
                UPDATE events e SET
                  article_count = sub.cnt,
                  centroid_embedding = sub.mean
                FROM (
                  SELECT count(*) AS cnt, avg(embedding) AS mean
                  FROM articles WHERE event_id = %s
                ) sub
                WHERE e.id = %s
                """,
                (event_id, event_id),
            )
    db_conn.commit()

    yield {"events": event_ids, "articles": article_ids}

    with db_conn.cursor() as cur:
        cur.execute(
            "DELETE FROM audit_log WHERE target = ANY(%s)", ([f"events/{e}" for e in event_ids],)
        )
        cur.execute("DELETE FROM articles WHERE source_id = %s", (source_id,))
        cur.execute("DELETE FROM event_entities WHERE event_id = ANY(%s)", (event_ids,))
        cur.execute("UPDATE events SET merged_into_id = NULL WHERE id = ANY(%s)", (event_ids,))
        cur.execute("DELETE FROM events WHERE merged_into_id = ANY(%s)", (event_ids,))
        cur.execute("DELETE FROM events WHERE id = ANY(%s)", (event_ids,))
        cur.execute("DELETE FROM sources WHERE id = %s", (source_id,))
    db_conn.commit()


def _state(db_conn, event_ids: list[int]) -> dict:  # noqa: ANN001
    """Geri alınabilirliğin ölçüldüğü durum: atama, sayım, birleştirme bayrağı.

    Merkez **bu karşılaştırmaya girmez** ve bu bilinçlidir. Merkez, üyelerden
    türetilen bir değerdir; sözleşmesi "üyelerinin ortalamasına eşit" olmasıdır,
    "bit düzeyinde aynı metni üretmesi" değil. SQL `avg()` ile Python
    ortalaması son basamakta ayrışır (float4 birikimi vs `%.6f` biçimlendirme);
    metin karşılaştırması bunu hata sanardı. Merkez ayrıca ve toleransla
    `_assert_centroids_match_members` ile denetlenir.
    """
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, article_count, merged_into_id
            FROM events WHERE id = ANY(%s) ORDER BY id
            """,
            (event_ids,),
        )
        events = {r["id"]: (r["article_count"], r["merged_into_id"]) for r in cur.fetchall()}
        cur.execute(
            "SELECT id, event_id FROM articles WHERE event_id = ANY(%s) ORDER BY id",
            (event_ids,),
        )
        articles = {r["id"]: r["event_id"] for r in cur.fetchall()}
    return {"events": events, "articles": articles}


def _assert_centroids_match_members(db_conn, event_ids: list[int]) -> None:  # noqa: ANN001
    """Merkez her zaman üyelerinin ortalaması olmalı (F2-02 sözleşmesi)."""
    with db_conn.cursor() as cur:
        for event_id in event_ids:
            cur.execute(
                "SELECT centroid_embedding::text AS c FROM events WHERE id = %s",
                (event_id,),
            )
            stored = cur.fetchone()["c"]
            cur.execute(
                "SELECT embedding::text AS e FROM articles "
                "WHERE event_id = %s AND embedding IS NOT NULL",
                (event_id,),
            )
            members = [[float(x) for x in r["e"].strip("[]").split(",")] for r in cur.fetchall()]
            expected = recompute(members)
            if expected is None:
                assert stored is None, f"olay {event_id}: üyesiz merkez NULL olmalı"
                continue
            actual = [float(x) for x in stored.strip("[]").split(",")]
            assert drift(actual, expected) < 1e-4, f"olay {event_id} merkezi kaymış"


def test_merge_then_undo_restores_exact_state(db_conn, fixtures) -> None:  # noqa: ANN001
    """G2 koşul 8: birleştirme %100 geri alınabilir."""
    source, target = fixtures["events"]
    before = _state(db_conn, fixtures["events"])

    result = merge_events(source, target)
    db_conn.commit()
    assert len(result.moved_article_ids) == 2
    _assert_centroids_match_members(db_conn, fixtures["events"])

    with db_conn.cursor() as cur:
        cur.execute("SELECT merged_into_id FROM events WHERE id = %s", (source,))
        assert cur.fetchone()["merged_into_id"] == target
    db_conn.commit()

    undo_merge(source)
    db_conn.commit()
    assert _state(db_conn, fixtures["events"]) == before
    _assert_centroids_match_members(db_conn, fixtures["events"])


def test_merged_event_is_marked_not_deleted(db_conn, fixtures) -> None:  # noqa: ANN001
    """Birleştirilen olay silinmez — geçmiş korunur (Spec §7.4)."""
    source, target = fixtures["events"]
    merge_events(source, target)
    db_conn.commit()
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM events WHERE id = %s", (source,))
        assert cur.fetchone()["n"] == 1
    db_conn.commit()


def test_split_then_undo_restores_exact_state(db_conn, fixtures) -> None:  # noqa: ANN001
    """G2 koşul 8: bölme %100 geri alınabilir."""
    source = fixtures["events"][0]
    before = _state(db_conn, fixtures["events"])

    result = split_event(source, fixtures["articles"][:1])
    db_conn.commit()
    _assert_centroids_match_members(db_conn, [source, result.new_event_id])

    undo_split(result.new_event_id)
    db_conn.commit()
    assert _state(db_conn, fixtures["events"]) == before
    _assert_centroids_match_members(db_conn, fixtures["events"])


def test_splitting_all_articles_is_rejected(db_conn, fixtures) -> None:  # noqa: ANN001
    """Sonuç boş bir olay olurdu — merkez tanımsız kalırdı."""
    source = fixtures["events"][0]
    with pytest.raises(MergeError, match="TÜM makaleleri"):
        split_event(source, fixtures["articles"][:2])
    db_conn.commit()


def test_split_rejects_articles_from_another_event(db_conn, fixtures) -> None:  # noqa: ANN001
    source = fixtures["events"][0]
    with pytest.raises(MergeError, match="bu olaya ait değil"):
        split_event(source, [fixtures["articles"][2]])
    db_conn.commit()


def test_event_cannot_merge_into_itself(db_conn, fixtures) -> None:  # noqa: ANN001
    with pytest.raises(MergeError, match="kendisiyle"):
        merge_events(fixtures["events"][0], fixtures["events"][0])
    db_conn.commit()


def test_merging_into_an_already_merged_event_is_rejected(db_conn, fixtures) -> None:  # noqa: ANN001
    """Zincir birleştirme, geri almayı belirsizleştirir."""
    source, target = fixtures["events"]
    merge_events(source, target)
    db_conn.commit()
    with pytest.raises(MergeError, match="zaten birleştirilmiş"):
        merge_events(source, target)
    db_conn.commit()


def test_undo_without_a_merge_record_is_rejected(db_conn, fixtures) -> None:  # noqa: ANN001
    """Kayıt yoksa geri alma yapılamaz — sessizce yanlış durum üretmez."""
    with pytest.raises(MergeError, match="birleştirilmemiş"):
        undo_merge(fixtures["events"][0])
    db_conn.commit()


def test_review_queue_and_resolution(db_conn, fixtures) -> None:  # noqa: ANN001
    """F2-04 DoD: belirsiz atamalar kuyrukta görünüyor, karar verilebiliyor."""
    event_id = fixtures["events"][0]
    with db_conn.cursor() as cur:
        cur.execute("UPDATE events SET review_flag = 'needs_review' WHERE id = %s", (event_id,))
    db_conn.commit()

    assert event_id in {r["id"] for r in review_queue(200)}

    resolve_review(event_id, "verified")
    db_conn.commit()
    assert event_id not in {r["id"] for r in review_queue(200)}

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM audit_log WHERE action = 'resolve_review' AND target = %s",
            (f"events/{event_id}",),
        )
        assert cur.fetchone()["n"] == 1
    db_conn.commit()


def test_invalid_review_decision_is_rejected(db_conn, fixtures) -> None:  # noqa: ANN001
    with pytest.raises(MergeError, match="verified"):
        resolve_review(fixtures["events"][0], "maybe")
    db_conn.commit()
