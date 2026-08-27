"""Phase 27: Ingestion SLO / SLI ve 101 Kaynak Gerçek Çalışma Mutabakatı."""

from __future__ import annotations

from datetime import UTC, datetime

from politikdesk.db import connection
from politikdesk.ingestion.sources import load_all_configs


def run_ingestion_slo_audit() -> dict:
    configs = load_all_configs()
    cfg_by_slug = {c.slug: c for c in configs}

    with connection() as conn, conn.cursor() as cur:
        # 1. Sources in DB
        cur.execute("""
            SELECT id, slug, name, kind, adapter, is_active, vertical
            FROM sources
            ORDER BY id;
        """)
        db_sources = [dict(r) for r in cur.fetchall()]

        # 2. Ingestion stats per source from articles table
        cur.execute("""
            SELECT 
                s.id as source_id,
                s.slug,
                s.name,
                s.adapter,
                s.is_active,
                count(a.id) as total_articles,
                min(a.first_seen_at) as first_seen,
                max(a.first_seen_at) as last_seen,
                count(a.id) FILTER (WHERE a.near_duplicate_of_id IS NOT NULL) as duplicates_count
            FROM sources s
            LEFT JOIN articles a ON a.source_id = s.id
            GROUP BY s.id, s.slug, s.name, s.adapter, s.is_active
            ORDER BY total_articles DESC;
        """)
        source_stats = [dict(r) for r in cur.fetchall()]

        # 3. Source fetch logs if available
        cur.execute("""
            SELECT 
                source_id,
                count(*) as total_fetches,
                count(*) FILTER (WHERE succeeded = true) as success_fetches,
                count(*) FILTER (WHERE succeeded = false) as error_fetches,
                avg(duration_ms) as avg_duration_ms,
                max(started_at) as last_fetch_time
            FROM source_fetch_log
            GROUP BY source_id;
        """)
        fetch_logs = {r["source_id"]: dict(r) for r in cur.fetchall()}

    now = datetime.now(UTC)
    reconciliation = []
    operating_count = 0
    rss_live_count = 0
    specialized_count = 0

    for s in source_stats:
        slug = s["slug"]
        s_id = s["source_id"]
        cfg = cfg_by_slug.get(slug)
        f_log = fetch_logs.get(s_id, {})

        last_seen = s["last_seen"]
        freshness_hrs = None
        if last_seen:
            diff = now - last_seen
            freshness_hrs = round(diff.total_seconds() / 3600.0, 1)

        total_arts = s["total_articles"]
        dup_count = s["duplicates_count"]
        dup_rate = round((dup_count / total_arts) * 100.0, 2) if total_arts > 0 else 0.0

        is_operating = total_arts > 0 or f_log.get("total_fetches", 0) > 0
        if is_operating:
            operating_count += 1
        if s["adapter"] == "rss":
            rss_live_count += 1
        else:
            specialized_count += 1

        reconciliation.append({
            "slug": slug,
            "name": s["name"],
            "adapter": s["adapter"],
            "is_active": s["is_active"],
            "in_config": cfg is not None,
            "total_articles": total_arts,
            "duplicate_rate": dup_rate,
            "last_seen": str(last_seen) if last_seen else None,
            "freshness_hours": freshness_hrs,
            "is_operating": is_operating,
            "fetch_success_rate": round(
                (f_log.get("success_fetches", 0) / f_log["total_fetches"]) * 100.0, 1
            ) if f_log.get("total_fetches", 0) > 0 else (100.0 if total_arts > 0 else 0.0),
        })

    return {
        "timestamp": now.isoformat(),
        "total_sources": len(db_sources),
        "operating_sources": operating_count,
        "rss_sources": rss_live_count,
        "specialized_sources": specialized_count,
        "sources": reconciliation,
    }


if __name__ == "__main__":
    res = run_ingestion_slo_audit()
    print(f"Total Sources: {res['total_sources']}")
    print(f"Operating Sources: {res['operating_sources']}")
    print(f"RSS Sources: {res['rss_sources']}")
    print(f"Specialized: {res['specialized_sources']}")
