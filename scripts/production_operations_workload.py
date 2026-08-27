"""Phase 27: Production-Like Uzun Süreli Eşzamanlı İş Yükü ve Trend Analizi."""

from __future__ import annotations

import concurrent.futures
import json
import time
import tracemalloc
from datetime import UTC, datetime

from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.db import connection, fetch_one
from politikdesk.web.repository import feed

client = TestClient(app)
AUTH = {"X-User-Id": "1"}


def run_operations_workload(iterations: int = 100) -> dict:
    tracemalloc.start()
    mem_start = tracemalloc.get_traced_memory()[0] / (1024 * 1024)

    # Initial DB & Connection state
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_database_size('politikdesk') as db_bytes;")
        db_start = fetch_one(cur)["db_bytes"]
        cur.execute("SELECT count(*) as total_conns FROM pg_stat_activity WHERE datname = 'politikdesk';")
        conn_start = fetch_one(cur)["total_conns"]

    api_latencies = []
    feed_latencies = []
    errors = 0

    t0 = time.perf_counter()

    def _worker_traffic(idx: int):
        nonlocal errors
        try:
            # 1. API Feed Read
            t_api = time.perf_counter()
            r = client.get("/feed?sort=important", headers=AUTH)
            lat_api = (time.perf_counter() - t_api) * 1000.0
            if r.status_code == 200:
                api_latencies.append(lat_api)
            else:
                errors += 1

            # 2. Filtered & Searched Feed
            t_feed = time.perf_counter()
            r_filt = client.get("/feed?category=ekonomi&sort=newest&q=faiz", headers=AUTH)
            lat_feed = (time.perf_counter() - t_feed) * 1000.0
            if r_filt.status_code == 200:
                feed_latencies.append(lat_feed)
            else:
                errors += 1

            # 3. Direct DB Repository Read
            items = feed(user_id=1, limit=10, category="ekonomi")
            assert isinstance(items, list)

            # 4. Live Check-New polling
            r_chk = client.get("/api/feed/check-new?since=2026-08-24T00:00:00Z", headers=AUTH)
            assert r_chk.status_code == 200

        except Exception:
            errors += 1

    # Run with 15 concurrent threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(_worker_traffic, i) for i in range(iterations)]
        concurrent.futures.wait(futures)

    duration_total = time.perf_counter() - t0

    # Final DB & Connection state
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_database_size('politikdesk') as db_bytes;")
        db_end = fetch_one(cur)["db_bytes"]
        cur.execute("SELECT count(*) as total_conns FROM pg_stat_activity WHERE datname = 'politikdesk';")
        conn_end = fetch_one(cur)["total_conns"]

    mem_end = tracemalloc.get_traced_memory()[0] / (1024 * 1024)
    mem_delta = mem_end - mem_start
    tracemalloc.stop()

    api_latencies.sort()
    feed_latencies.sort()

    n_api = len(api_latencies)
    n_feed = len(feed_latencies)

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "total_requests_executed": iterations * 4,
        "duration_seconds": round(duration_total, 2),
        "rps": round((iterations * 4) / duration_total, 2) if duration_total > 0 else 0,
        "error_count": errors,
        "error_rate": round((errors / (iterations * 4)) * 100.0, 3),
        "api_p50_ms": round(api_latencies[int(n_api * 0.50)], 2) if n_api else 0,
        "api_p95_ms": round(api_latencies[int(n_api * 0.95)], 2) if n_api else 0,
        "api_p99_ms": round(api_latencies[min(int(n_api * 0.99), n_api - 1)], 2) if n_api else 0,
        "feed_p50_ms": round(feed_latencies[int(n_feed * 0.50)], 2) if n_feed else 0,
        "feed_p95_ms": round(feed_latencies[int(n_feed * 0.95)], 2) if n_feed else 0,
        "memory_start_mb": round(mem_start, 2),
        "memory_end_mb": round(mem_end, 2),
        "memory_delta_mb": round(mem_delta, 2),
        "db_bytes_start": db_start,
        "db_bytes_end": db_end,
        "db_growth_bytes": db_end - db_start,
        "connections_start": conn_start,
        "connections_end": conn_end,
    }


if __name__ == "__main__":
    res = run_operations_workload(iterations=125)
    print(json.dumps(res, indent=2, default=str))
