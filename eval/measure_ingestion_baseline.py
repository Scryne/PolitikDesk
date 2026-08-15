import psycopg

conn_str = "postgresql://politikdesk:politikdesk@127.0.0.1:5432/politikdesk"

with psycopg.connect(conn_str) as conn, conn.cursor() as cur:
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    tables = [r[0] for r in cur.fetchall()]
    
    # Check source logs / health report tables
    print("Existing tables:", sorted(tables))
    
    for table in ["source_fetch_log", "sources", "audit_log", "articles"]:
        if table in tables:
            cur.execute(
                f"SELECT column_name, data_type FROM information_schema.columns "
                f"WHERE table_name='{table}'"
            )
            cols = cur.fetchall()
            print(f"\n--- Table: {table} columns ---")
            for c in cols:
                print(f"  {c[0]}: {c[1]}")

    # Check source_fetch_log content if exists
    if "source_fetch_log" in tables:
        cur.execute("SELECT count(*) FROM source_fetch_log")
        total_all_time = cur.fetchone()[0]
        print(f"\nTotal rows in source_fetch_log: {total_all_time}")

        cur.execute("""
            SELECT 
                count(*) as total_attempts,
                count(*) FILTER (WHERE succeeded = true) as success_count,
                count(*) FILTER (WHERE succeeded = false) as failure_count,
                avg(duration_ms) as avg_duration,
                max(duration_ms) as max_duration
            FROM source_fetch_log
            WHERE started_at >= NOW() - INTERVAL '24 hours'
        """)
        row = cur.fetchone()
        print(
            f"Last 24h Summary: Total={row[0]}, Success={row[1]}, Failure={row[2]}, "
            f"AvgDuration={row[3]:.1f}ms, MaxDuration={row[4]}ms"
        )
        if row[0] > 0:
            print(f"Failure Rate: {row[2]/row[0]*100:.2f}%")

        cur.execute("""
            SELECT 
                s.slug,
                s.adapter,
                count(l.id) as total,
                count(l.id) FILTER (WHERE l.succeeded = false) as fails,
                avg(l.duration_ms) as avg_duration,
                max(l.started_at) FILTER (WHERE l.succeeded = true) as last_success,
                max(l.started_at) FILTER (WHERE l.succeeded = false) as last_failure
            FROM sources s
            LEFT JOIN source_fetch_log l ON s.id = l.source_id AND l.started_at >= NOW() - INTERVAL '24 hours'
            GROUP BY s.slug, s.adapter
            ORDER BY fails DESC, total DESC
        """)
        print("\nBy Source (Last 24h):")
        for r in cur.fetchall():
            fail_pct = (r[3] / r[2] * 100) if r[2] and r[2] > 0 else 0
            avg_d = f"{r[4]:.0f}ms" if r[4] else "N/A"
            print(
                f"  {r[0]:<25} (adapter={r[1]:<14}): total={r[2]:<4} fails={r[3]:<4} "
                f"({fail_pct:5.1f}%) avg={avg_d:<7} | last_success={r[5]} | last_fail={r[6]}"
            )

        cur.execute("""
            SELECT 
                s.slug,
                l.error,
                count(*) as occ
            FROM source_fetch_log l
            JOIN sources s ON s.id = l.source_id
            WHERE l.started_at >= NOW() - INTERVAL '24 hours' AND l.succeeded = false
            GROUP BY s.slug, l.error
            ORDER BY occ DESC
        """)
        print("\nFailure Breakdown by Source & Error (Last 24h):")
        for r in cur.fetchall():
            print(f"  [{r[2]}x] {r[0]}: {r[1]}")

    # Also inspect sources table
    if "sources" in tables:
        cur.execute(
            "SELECT slug, name, adapter, is_active, last_fetched_at, "
            "last_success_at, consecutive_errors, last_error FROM sources"
        )
        print("\nSources State in 'sources' table:")
        for r in cur.fetchall():
            print(
                f"  {r[0]:<25} (adapter={r[2]}, active={r[3]}): "
                f"consecutive_errors={r[6]} | last_fetch={r[4]} | "
                f"last_success={r[5]} | last_error={r[7]}"
            )


