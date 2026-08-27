"""Phase 27: Canlı Üretim Telemetrisi Toplama Scripti."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from politikdesk.db import connection, fetch_one


def collect_telemetry() -> dict:
    with connection() as conn, conn.cursor() as cur:
        # Connections
        cur.execute("""
            SELECT count(*) AS total_conns,
                   count(*) FILTER (WHERE state = 'active') AS active_conns,
                   count(*) FILTER (WHERE state = 'idle') AS idle_conns,
                   count(*) FILTER (WHERE wait_event_type IS NOT NULL) AS waiting_conns
            FROM pg_stat_activity WHERE datname = 'politikdesk';
        """)
        conns = dict(fetch_one(cur))

        # DB Size
        cur.execute("SELECT pg_size_pretty(pg_database_size('politikdesk')) AS db_size, pg_database_size('politikdesk') AS db_bytes;")
        db_size = dict(fetch_one(cur))

        # Table Sizes
        cur.execute("""
            SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
                   pg_total_relation_size(relid) AS size_bytes
            FROM pg_catalog.pg_statio_user_tables
            ORDER BY pg_total_relation_size(relid) DESC LIMIT 15;
        """)
        table_sizes = [dict(r) for r in cur.fetchall()]

        # Cache hit ratio
        cur.execute("""
            SELECT sum(heap_blks_read) as blks_read, sum(heap_blks_hit)  as blks_hit,
                   round(sum(heap_blks_hit) * 100.0 / nullif(sum(heap_blks_hit) + sum(heap_blks_read), 0), 2) as cache_hit_ratio
            FROM pg_statio_user_tables;
        """)
        cache_stats = dict(fetch_one(cur))

        # Transaction stats
        cur.execute("""
            SELECT xact_commit, xact_rollback, conflicts, deadlocks
            FROM pg_stat_database WHERE datname = 'politikdesk';
        """)
        xact_stats = dict(fetch_one(cur))

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "connections": conns,
        "database_size": db_size,
        "top_tables": table_sizes,
        "cache": cache_stats,
        "transactions": xact_stats,
    }


if __name__ == "__main__":
    data = collect_telemetry()
    print(json.dumps(data, indent=2, default=str))
