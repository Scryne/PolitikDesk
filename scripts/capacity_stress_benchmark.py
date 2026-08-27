"""Phase 27: Progressive Real Capacity & Saturation Benchmark."""

from __future__ import annotations

import concurrent.futures
import json
import statistics
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

import redis

from politikdesk.config import get_settings
from politikdesk.db import connection, fetch_one

BASE_URL = "http://127.0.0.1:8000"


def get_system_telemetry() -> dict[str, Any]:
    # DB Connections
    db_conns = {}
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT count(*) as total, 
                       count(*) FILTER (WHERE state = 'active') as active,
                       count(*) FILTER (WHERE state = 'idle') as idle
                FROM pg_stat_activity WHERE datname = 'politikdesk';
            """)
            db_conns = dict(fetch_one(cur))
    except Exception as e:
        db_conns = {"error": str(e)}

    # Redis Queue & Memory
    redis_stats = {}
    try:
        settings = get_settings()
        r = redis.Redis.from_url(settings.redis_url)
        info_mem = r.info("memory")
        redis_stats = {
            "used_memory_human": info_mem.get("used_memory_human"),
            "used_memory_rss_human": info_mem.get("used_memory_rss_human"),
            "celery_queue_len": r.llen("celery"),
            "celery_llm_queue_len": r.llen("celery:llm"),
        }
    except Exception as e:
        redis_stats = {"error": str(e)}

    return {
        "db_connections": db_conns,
        "redis": redis_stats,
    }


def benchmark_tier(concurrency: int, total_requests: int, endpoint: str = "/health/live") -> dict[str, Any]:
    url = f"{BASE_URL}{endpoint}"
    latencies: list[float] = []
    errors = 0
    timeouts = 0

    t_before = get_system_telemetry()
    t_start = time.perf_counter()

    def _fetch(_: int):
        nonlocal errors, timeouts
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PolitikDesk-Capacity-Bench/1.0"})
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                _ = resp.read()
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                latencies.append(elapsed_ms)
        except urllib.error.URLError as e:
            if "timed out" in str(e).lower():
                timeouts += 1
            else:
                errors += 1
        except Exception:
            errors += 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(_fetch, i) for i in range(total_requests)]
        concurrent.futures.wait(futures)

    duration = time.perf_counter() - t_start
    t_after = get_system_telemetry()

    latencies.sort()
    n = len(latencies)
    rps = round(n / duration, 2) if duration > 0 else 0.0

    p50 = round(latencies[int(n * 0.50)], 2) if n > 0 else 0.0
    p90 = round(latencies[int(n * 0.90)], 2) if n > 0 else 0.0
    p95 = round(latencies[int(n * 0.95)], 2) if n > 0 else 0.0
    p99 = round(latencies[min(int(n * 0.99), n - 1)], 2) if n > 0 else 0.0
    max_lat = round(latencies[-1], 2) if n > 0 else 0.0
    mean_lat = round(statistics.mean(latencies), 2) if n > 0 else 0.0

    error_rate = round((errors / total_requests) * 100.0, 2) if total_requests > 0 else 0.0
    timeout_rate = round((timeouts / total_requests) * 100.0, 2) if total_requests > 0 else 0.0

    return {
        "concurrency": concurrency,
        "total_requests": total_requests,
        "successful_requests": n,
        "duration_seconds": round(duration, 3),
        "rps": rps,
        "latencies_ms": {
            "p50": p50,
            "p90": p90,
            "p95": p95,
            "p99": p99,
            "mean": mean_lat,
            "max": max_lat,
        },
        "errors": errors,
        "timeouts": timeouts,
        "error_rate_pct": error_rate,
        "timeout_rate_pct": timeout_rate,
        "telemetry_before": t_before,
        "telemetry_after": t_after,
    }


def run_progressive_capacity_benchmark() -> dict[str, Any]:
    tiers = [
        (10, 200),
        (25, 500),
        (50, 1000),
        (100, 1500),
        (200, 2000),
    ]

    results = []
    print("Starting Progressive Capacity Benchmark...")
    for conc, reqs in tiers:
        print(f"Testing concurrency={conc}, requests={reqs}...")
        res = benchmark_tier(conc, reqs)
        results.append(res)
        print(f" -> Concurrency {conc}: RPS={res['rps']}, p95={res['latencies_ms']['p95']}ms, Error%={res['error_rate_pct']}")
        time.sleep(1.0)

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "tiers": results,
    }


if __name__ == "__main__":
    out = run_progressive_capacity_benchmark()
    with open("CAPACITY_BENCHMARK_RAW.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print("Benchmark complete. Saved to CAPACITY_BENCHMARK_RAW.json")
