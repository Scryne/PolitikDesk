"""Phase 5.8: Database Performance & EXPLAIN ANALYZE Benchmark.

Runs EXPLAIN (ANALYZE, BUFFERS) on:
1. Historical context pending query (AUDIT-005)
2. Historical context vector similarity search
3. Clustering pending query (AUDIT-001)
4. Read-first user query (AUDIT-004)
"""

from __future__ import annotations

from politikdesk.db import connection


def analyze_queries() -> None:
    print("=================================================================")
    print("PHASE 5.8 DATABASE PERFORMANCE & EXPLAIN ANALYZE BENCHMARK")
    print("=================================================================")

    with connection() as conn, conn.cursor() as cur:
        # 1. Historical Context Pending Query (AUDIT-005)
        print("\n--- 1. Context Pending Query (AUDIT-005) ---")
        q1 = """
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT e.id FROM events e
        WHERE e.merged_into_id IS NULL
          AND e.centroid_embedding IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM event_relations r WHERE r.from_event_id = e.id
          )
          AND NOT EXISTS (
            SELECT 1 FROM audit_log a
            WHERE a.target = 'events/' || e.id
              AND a.action = 'context_evaluated'
              AND a.created_at >= e.last_update_at
          )
        ORDER BY e.last_update_at DESC
        LIMIT 50;
        """
        cur.execute(q1)
        plan1 = "\n".join(r["QUERY PLAN"] for r in cur.fetchall())
        print(plan1)

        # 2. Read-First User Query (AUDIT-004)
        print("\n--- 2. Read-First User Query (AUDIT-004) ---")
        q2 = """
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT id FROM users WHERE email = 'editor@politikdesk.local';
        """
        cur.execute(q2)
        plan2 = "\n".join(r["QUERY PLAN"] for r in cur.fetchall())
        print(plan2)

        # 3. Clustering Pending Query (AUDIT-001)
        print("\n--- 3. Clustering Pending Query (AUDIT-001) ---")
        q3 = """
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT a.id, a.title, a.excerpt, a.published_at, a.first_seen_at,
               a.embedding::text AS embedding,
               COALESCE(a.vertical, s.vertical, 'macro_economy') AS vertical
        FROM articles a
        LEFT JOIN sources s ON s.id = a.source_id
        WHERE a.event_id IS NULL
          AND a.embedding IS NOT NULL
          AND a.entities_extracted_at IS NOT NULL
        ORDER BY COALESCE(a.published_at, a.first_seen_at)
        LIMIT 50;
        """
        cur.execute(q3)
        plan3 = "\n".join(r["QUERY PLAN"] for r in cur.fetchall())
        print(plan3)


if __name__ == "__main__":
    analyze_queries()
