"""Phase 5.2 & 5.3: Real PostgreSQL Concurrency & Failure Verification.

Executes real multi-threaded concurrency against live PostgreSQL with 2, 5, and 10 workers.
Proves that under real database transaction conditions:
- 1 unclustered article + N concurrent workers -> exactly 1 event created, 0 orphan events.
- Losing workers cleanly rollback.
- Invariants hold without partial state.
"""

from __future__ import annotations

import concurrent.futures
import threading
import time
from datetime import UTC, datetime
from typing import Any

from politikdesk.clustering.assigner import ArticleFeatures, Assignment
from politikdesk.clustering.repository import assign_article, create_event
from politikdesk.db import connection, fetch_one


def setup_test_article(title_suffix: str) -> tuple[int, ArticleFeatures, dict[str, Any]]:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sources (slug, name, tier, kind, access_method, tos_status, vertical)
            VALUES (%s, %s, 1, 'official', 'api', 'allowed', 'macro_economy')
            ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            ("test-phase5-src", "Test Phase5 Source"),
        )
        source_id = fetch_one(cur)["id"]

        unique_key = f"{title_suffix}_{time.time_ns()}"
        url = f"https://example.com/phase5-test-{unique_key}"
        cur.execute(
            """
            INSERT INTO articles (source_id, vertical, canonical_url, title, excerpt, content_hash,
                                  published_at, first_seen_at, raw_purge_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                source_id,
                "macro_economy",
                url,
                f"Phase 5 Test Article {title_suffix}",
                "Test excerpt content for concurrency verification",
                f"hash_{unique_key}",
                datetime.now(UTC),
                datetime.now(UTC),
                datetime.now(UTC),
            ),
        )
        article_id = int(fetch_one(cur)["id"])
        conn.commit()

    article_features = ArticleFeatures(
        article_id=article_id,
        embedding=[0.01] * 1024,
        entities=frozenset(["TCMB"]),
        key_entities=frozenset(["TCMB"]),
        published_at=datetime.now(UTC),
        vertical="macro_economy",
    )
    row = {
        "id": article_id,
        "title": f"Phase 5 Test Article {title_suffix}",
        "excerpt": "Test excerpt content for concurrency verification",
    }
    return article_id, article_features, row


def test_concurrent_event_creation(worker_count: int) -> dict[str, Any]:
    print(f"\n--- Testing Concurrent create_event with {worker_count} workers ---")
    article_id, article_features, row = setup_test_article(f"workers_{worker_count}")

    barrier = threading.Barrier(worker_count)
    results: list[int | None] = []

    def worker_func(w_id: int) -> int | None:
        barrier.wait()  # Synchronize all threads to fire simultaneously
        res = create_event(article_features, row)
        return res

    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(worker_func, i) for i in range(worker_count)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    non_none_results = [r for r in results if r is not None]
    print(f"Workers: {worker_count}, Outcomes: {results}, Successes: {len(non_none_results)}")

    # Verify database state
    with connection() as conn, conn.cursor() as cur:
        # Check article's assigned event_id
        cur.execute("SELECT event_id FROM articles WHERE id = %s", (article_id,))
        art_event_id = cur.fetchone()["event_id"]

        # Check total events created with this title
        cur.execute(
            "SELECT id, article_count FROM events WHERE title = %s",
            (row["title"],),
        )
        events_found = cur.fetchall()

        # Check orphan events
        cur.execute(
            """
            SELECT e.id FROM events e
            WHERE e.title = %s
              AND NOT EXISTS (SELECT 1 FROM articles a WHERE a.event_id = e.id)
            """,
            (row["title"],),
        )
        orphan_events = cur.fetchall()

    print(f"Article event_id in DB: {art_event_id}")
    print(f"Total events in DB: {len(events_found)}")
    print(f"Orphan events in DB: {len(orphan_events)}")

    assert len(non_none_results) == 1, (
        f"Expected exactly 1 successful worker, got {len(non_none_results)}"
    )
    assert len(events_found) == 1, (
        f"Expected exactly 1 event created in DB, got {len(events_found)}"
    )
    assert len(orphan_events) == 0, f"Expected 0 orphan events, got {len(orphan_events)}"
    assert art_event_id == non_none_results[0], (
        f"Article event_id {art_event_id} mismatch with winner {non_none_results[0]}"
    )

    return {
        "workers": worker_count,
        "success_count": len(non_none_results),
        "total_events": len(events_found),
        "orphan_events": len(orphan_events),
        "winner_event_id": non_none_results[0],
    }


def test_concurrent_event_assignment(worker_count: int) -> dict[str, Any]:
    print(f"\n--- Testing Concurrent assign_article with {worker_count} workers ---")
    article_id, article_features, row = setup_test_article(f"assign_{worker_count}")

    # Create target event first
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO events (title, summary, vertical, centroid_embedding,
                                first_reported_at, last_update_at, article_count)
            VALUES (%s, %s, %s, %s::vector, %s, %s, 1)
            RETURNING id
            """,
            (
                f"Target Cluster Event {time.time_ns()}",
                "Summary",
                "macro_economy",
                f"[{','.join(['0.01'] * 1024)}]",
                datetime.now(UTC),
                datetime.now(UTC),
            ),
        )
        target_event_id = int(fetch_one(cur)["id"])
        conn.commit()

    barrier = threading.Barrier(worker_count)
    decision = Assignment(action="assign", event_id=target_event_id, similarity=0.95)
    results: list[bool] = []

    def worker_func(w_id: int) -> bool:
        barrier.wait()
        return assign_article(article_features, decision)

    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(worker_func, i) for i in range(worker_count)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    success_count = sum(1 for r in results if r is True)
    print(f"Workers: {worker_count}, Assign Outcomes: {results}, Successes: {success_count}")

    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT event_id FROM articles WHERE id = %s", (article_id,))
        art_event_id = cur.fetchone()["event_id"]

        cur.execute("SELECT article_count FROM events WHERE id = %s", (target_event_id,))
        article_count = cur.fetchone()["article_count"]

    print(f"Article event_id: {art_event_id}, Target event article_count: {article_count}")

    assert success_count == 1, f"Expected exactly 1 successful assign, got {success_count}"
    assert art_event_id == target_event_id, "Article must be assigned to target event"
    assert article_count == 2, (
        f"Target event article_count should be exactly 2, got {article_count}"
    )

    return {
        "workers": worker_count,
        "success_count": success_count,
        "final_article_count": article_count,
    }


def main() -> None:
    print("=================================================================")
    print("PHASE 5.2 REAL POSTGRESQL CONCURRENCY VALIDATION")
    print("=================================================================")

    for n in [2, 5, 10]:
        _ = test_concurrent_event_creation(n)
        print(f"PASS: {n} concurrent create_event -> 1 event, 0 orphans")
        _ = test_concurrent_event_assignment(n)
        print(f"PASS: {n} concurrent assign_article -> 1 winner, accurate article_count")

    print("\n[ALL POSTGRESQL CONCURRENCY RUNTIME BENCHMARKS PASSED SUCCESSFULLY]")


if __name__ == "__main__":
    main()
