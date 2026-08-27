"""Search Performance & Trigram GIN Certification Benchmark (Phase 28 / Phase B).

Measures:
1. PostgreSQL planner index selection (EXPLAIN ANALYZE: Bitmap Index Scan vs Seq Scan).
2. Latency percentiles (p50, p95, p99, mean, max) across 7 query classes:
   - Exact-ish search (`%ekonomi%`)
   - Substring search (`%merkez bankası%`)
   - Short query (`faiz`)
   - Long query (`Türkiye Cumhuriyet Merkez Bankası politika faizi`)
   - Turkish characters (`ş`, `ğ`, `ı`, `İ`, `ö`, `ü`, `ç`)
   - Low selectivity (matches large subset)
   - High selectivity (matches 1-2 records)
3. Scaling curve across dataset tiers:
   - Tier 1: Real dataset (12,770 articles, 3,685 events)
   - Tier 2: 50,000 records
   - Tier 3: 100,000 records
   - Tier 4: 250,000 records
"""

from __future__ import annotations

import statistics
import time
from typing import Any

from politikdesk.db import connection

QUERY_CLASSES = [
    ("exact_ish", "SELECT count(*) FROM events WHERE title ILIKE '%ekonomi%'"),
    ("substring", "SELECT count(*) FROM events WHERE title ILIKE '%merkez bankası%'"),
    ("short_query", "SELECT count(*) FROM events WHERE title ILIKE '%faiz%'"),
    (
        "long_query",
        "SELECT count(*) FROM events WHERE title ILIKE '%Türkiye Cumhuriyet Merkez Bankası politika faizi%'",
    ),
    ("turkish_chars", "SELECT count(*) FROM events WHERE title ILIKE '%şirket%' OR title ILIKE '%çağrı%'"),
    ("low_selectivity", "SELECT count(*) FROM events WHERE title ILIKE '%ve%'"),
    ("high_selectivity", "SELECT count(*) FROM events WHERE title ILIKE '%Hazine ve Maliye Bakanlığı 2026 Ağustos%'"),
]


def explain_query(sql: str) -> tuple[str, float]:
    """Runs EXPLAIN (ANALYZE, BUFFERS) and extracts the execution plan and execution time."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}")
        row = cur.fetchone()
        assert row is not None
        plan_json = list(row.values())[0]
        root_node = plan_json[0]["Plan"]
        exec_time = plan_json[0]["Execution Time"]

        # Traverse plan to find scan type and index
        def find_scans(node: dict[str, Any]) -> list[str]:
            scans = []
            node_type = node.get("Node Type", "")
            idx_name = node.get("Index Name", "")
            if idx_name:
                scans.append(f"{node_type} ({idx_name})")
            elif "Scan" in node_type:
                scans.append(node_type)
            for child in node.get("Plans", []):
                scans.extend(find_scans(child))
            return scans

        scans = find_scans(root_node)
        scan_desc = " -> ".join(scans) if scans else root_node.get("Node Type", "Unknown")
        return scan_desc, exec_time


def benchmark_query_latency(sql: str, iterations: int = 50) -> dict[str, float]:
    """Runs repeated queries to measure p50, p95, p99, mean, max latency in ms."""
    latencies: list[float] = []
    with connection() as conn, conn.cursor() as cur:
        # Warm-up
        cur.execute(sql)
        cur.fetchall()

        for _ in range(iterations):
            t0 = time.perf_counter()
            cur.execute(sql)
            cur.fetchall()
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)

    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    mean_val = statistics.mean(latencies)
    max_val = max(latencies)
    return {
        "p50": round(p50, 3),
        "p95": round(p95, 3),
        "p99": round(p99, 3),
        "mean": round(mean_val, 3),
        "max": round(max_val, 3),
        "qps": round(1000.0 / mean_val, 1) if mean_val > 0 else 0.0,
    }


def run_tier_benchmarks() -> dict[str, Any]:
    """Executes the complete search performance benchmark."""
    results: dict[str, Any] = {"real_dataset": {}}

    # 1. Real Database Stats
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT version();")
        r = cur.fetchone()
        assert r is not None
        pg_ver = str(list(r.values())[0])

        cur.execute("SELECT count(*) FROM events;")
        r = cur.fetchone()
        assert r is not None
        event_count = int(list(r.values())[0])

        cur.execute("SELECT count(*) FROM articles;")
        r = cur.fetchone()
        assert r is not None
        article_count = int(list(r.values())[0])

        cur.execute("SELECT pg_size_pretty(pg_relation_size('idx_events_title_trgm'));")
        r = cur.fetchone()
        assert r is not None
        idx_size = str(list(r.values())[0])

        cur.execute("SELECT pg_size_pretty(pg_total_relation_size('events'));")
        r = cur.fetchone()
        assert r is not None
        table_size = str(list(r.values())[0])

    results["metadata"] = {
        "postgres_version": pg_ver,
        "events_count": event_count,
        "articles_count": article_count,
        "index_size_idx_events_title_trgm": idx_size,
        "table_size_events": table_size,
    }

    print(f"[*] Environment: {pg_ver.split(',')[0]}")
    print(f"[*] Real Data: {event_count:,} events, {article_count:,} articles. Index Size: {idx_size}")

    for qname, sql in QUERY_CLASSES:
        scan_desc, explain_exec_ms = explain_query(sql)
        stats = benchmark_query_latency(sql, iterations=40)
        results["real_dataset"][qname] = {
            "sql": sql,
            "scan_type": scan_desc,
            "explain_exec_ms": round(explain_exec_ms, 3),
            "latency_stats": stats,
        }
        print(f"  [{qname:18}] Plan: {scan_desc:35} | p50: {stats['p50']:5.2f}ms | p95: {stats['p95']:5.2f}ms | QPS: {stats['qps']}")

    # 2. Synthetic Tiered Scaling Benchmark (dedicated bench table with pg_trgm index)
    print("\n[*] Running Synthetic Scale Tiers (50k, 100k, 250k records)...")
    results["scale_tiers"] = {}

    with connection() as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS bench_events_scale;")
        cur.execute(
            """
            CREATE UNLOGGED TABLE bench_events_scale (
                id serial PRIMARY KEY,
                title text NOT NULL,
                summary text
            );
            """
        )
        cur.execute("CREATE INDEX idx_bench_events_title_trgm ON bench_events_scale USING gin (title gin_trgm_ops);")
        conn.commit()

        # Base Turkish phrases for realistic combinatorial generator
        actors = ["TCMB", "TÜİK", "Hazine ve Maliye Bakanlığı", "BDDK", "SPK", "TBMM", "Cumhurbaşkanlığı", "FED", "ECB"]
        actions = [
            "faiz kararını açıkladı",
            "enflasyon verilerini yayımladı",
            "bütçe dengesini duyurdu",
            "yeni düzenleme getirdi",
            "ekonomik reform paketini sundu",
            "politika metnini paylaştı",
        ]
        topics = [
            "makro ekonomi göstergeleri",
            "yıllık TÜFE oranları",
            "dış ticaret dengesi",
            "finansal istikrar raporu",
            "kamu maliyesi hedefleri",
            "para politikası operasyonları",
        ]

        tier_counts = [50000, 100000, 250000]
        current_rows = 0

        for target_count in tier_counts:
            cur.execute(
                f"""
                INSERT INTO bench_events_scale (title, summary)
                SELECT
                    (ARRAY{actors})[1 + (g % {len(actors)})] || ' ' ||
                    (ARRAY{actions})[1 + ((g / {len(actors)}) % {len(actions)})] || ': ' ||
                    (ARRAY{topics})[1 + ((g / ({len(actors)} * {len(actions)})) % {len(topics)})] || ' [Kayıt ' || g || ']',
                    'Bu kayıt performans kıyaslaması için otomatik üretilmiştir. Detay metni ' || g
                FROM generate_series({current_rows + 1}, {target_count}) AS g;
                """
            )
            current_rows = target_count
            cur.execute("ANALYZE bench_events_scale;")
            conn.commit()
            cur.execute("SELECT pg_size_pretty(pg_relation_size('idx_bench_events_title_trgm'));")
            r = cur.fetchone()
            assert r is not None
            tier_idx_size = str(list(r.values())[0])

            tier_key = f"{target_count // 1000}k_records"
            results["scale_tiers"][tier_key] = {"index_size": tier_idx_size}

            test_sql = "SELECT count(*) FROM bench_events_scale WHERE title ILIKE '%enflasyon verilerini%'"
            scan_desc, explain_exec_ms = explain_query(test_sql)
            stats = benchmark_query_latency(test_sql, iterations=30)

            results["scale_tiers"][tier_key]["substring_search"] = {
                "scan_type": scan_desc,
                "explain_exec_ms": round(explain_exec_ms, 3),
                "latency_stats": stats,
            }
            print(f"  Tier {tier_key:12} (Index: {tier_idx_size:8}): {scan_desc:35} | p50: {stats['p50']:5.2f}ms | p95: {stats['p95']:5.2f}ms | QPS: {stats['qps']}")

        # Teardown benchmark table
        cur.execute("DROP TABLE IF EXISTS bench_events_scale;")
        conn.commit()
        print("[*] Benchmark table bench_events_scale dropped.")

    return results


if __name__ == "__main__":
    res = run_tier_benchmarks()
