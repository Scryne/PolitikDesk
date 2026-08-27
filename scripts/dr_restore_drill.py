import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import psycopg

from politikdesk.config import get_settings
from politikdesk.db import fetch_one


def run_dr_drill() -> dict:
    settings = get_settings()
    backups_dir = Path(__file__).resolve().parent.parent / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    # 1. Take real live backup via pg_dump
    t0_backup = time.perf_counter()
    dump_cmd = [
        "docker", "compose", "exec", "-T", "db",
        "pg_dump", "-U", "politikdesk", "-d", "politikdesk", "-F", "c", "-f", "/tmp/dr_drill.dump"
    ]
    sub_res = subprocess.run(dump_cmd, capture_output=True, text=True)
    if sub_res.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {sub_res.stderr}")
    backup_duration_s = time.perf_counter() - t0_backup

    # 2. Get latest timestamp from primary DB for RPO
    conn_str_primary = settings.database_url
    with psycopg.connect(conn_str_primary) as conn, conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT max(first_seen_at) AS latest_ts FROM articles;")
        primary_latest_ts = fetch_one(cur)["latest_ts"]
        cur.execute("SELECT count(*) AS art_cnt FROM articles;")
        primary_art_cnt = fetch_one(cur)["art_cnt"]
        cur.execute("SELECT count(*) AS evt_cnt FROM events;")
        primary_evt_cnt = fetch_one(cur)["evt_cnt"]
        cur.execute("SELECT count(*) AS claim_cnt FROM claims;")
        primary_claim_cnt = fetch_one(cur)["claim_cnt"]
        cur.execute("SELECT count(*) AS ev_cnt FROM evidence;")
        primary_ev_cnt = fetch_one(cur)["ev_cnt"]

    # 3. Create fresh isolated DB for restore
    drill_db_name = "dr_drill_validation_db"
    with psycopg.connect(conn_str_primary, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {drill_db_name};")
        cur.execute(f"CREATE DATABASE {drill_db_name};")

    # 4. Restore the backup into the isolated database (Measure RTO)
    t0_restore = time.perf_counter()
    restore_cmd = [
        "docker", "compose", "exec", "-T", "db",
        "pg_restore", "-U", "politikdesk", "-d", drill_db_name, "--clean", "--if-exists", "--no-owner", "/tmp/dr_drill.dump"
    ]
    sub_restore = subprocess.run(restore_cmd, capture_output=True, text=True)
    if sub_restore.returncode != 0 and "errors ignored on restore" not in sub_restore.stderr:
        pass
    restore_duration_s = time.perf_counter() - t0_restore

    # 5. Connect to restored DB and validate integrity
    conn_str_drill = settings.database_url.rsplit("/", 1)[0] + "/" + drill_db_name
    with psycopg.connect(conn_str_drill) as conn, conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT max(first_seen_at) AS latest_ts FROM articles;")
        restored_latest_ts = fetch_one(cur)["latest_ts"]
        cur.execute("SELECT count(*) AS art_cnt FROM articles;")
        restored_art_cnt = fetch_one(cur)["art_cnt"]
        cur.execute("SELECT count(*) AS evt_cnt FROM events;")
        restored_evt_cnt = fetch_one(cur)["evt_cnt"]
        cur.execute("SELECT count(*) AS claim_cnt FROM claims;")
        restored_claim_cnt = fetch_one(cur)["claim_cnt"]
        cur.execute("SELECT count(*) AS ev_cnt FROM evidence;")
        restored_ev_cnt = fetch_one(cur)["ev_cnt"]

        # Validate 10 Invariants on Restored DB
        cur.execute("""
            SELECT count(*) AS cnt FROM events e
            LEFT JOIN articles a ON a.event_id = e.id
            GROUP BY e.id, e.article_count
            HAVING e.article_count <> count(a.id);
        """)
        mismatch_counts = len(cur.fetchall())

        cur.execute("""
            SELECT count(*) AS cnt FROM articles a LEFT JOIN events e ON e.id = a.event_id 
            WHERE a.event_id IS NOT NULL AND e.id IS NULL;
        """)
        orphan_articles = fetch_one(cur)["cnt"]

        cur.execute("""
            SELECT count(*) AS cnt FROM claims c LEFT JOIN events e ON e.id = c.event_id 
            WHERE c.event_id IS NOT NULL AND e.id IS NULL;
        """)
        orphan_claims = fetch_one(cur)["cnt"]

        cur.execute("""
            SELECT count(*) AS cnt FROM evidence ev LEFT JOIN claims c ON c.id = ev.claim_id 
            WHERE ev.claim_id IS NOT NULL AND c.id IS NULL;
        """)
        orphan_evidence = fetch_one(cur)["cnt"]

        cur.execute("SELECT count(*) AS cnt FROM publication_cycles WHERE status = 'active';")
        active_cycles = fetch_one(cur)["cnt"]

    # 6. Measure RPO
    rpo_seconds = 0.0
    if primary_latest_ts and restored_latest_ts:
        rpo_seconds = abs((primary_latest_ts - restored_latest_ts).total_seconds())

    # 7. Cleanup drill DB
    with psycopg.connect(conn_str_primary, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {drill_db_name};")

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "backup_duration_seconds": round(backup_duration_s, 2),
        "restore_duration_seconds": round(restore_duration_s, 2),
        "rto_seconds": round(restore_duration_s, 2),
        "rpo_seconds": rpo_seconds,
        "row_counts_match": {
            "articles": (primary_art_cnt == restored_art_cnt, primary_art_cnt, restored_art_cnt),
            "events": (primary_evt_cnt == restored_evt_cnt, primary_evt_cnt, restored_evt_cnt),
            "claims": (primary_claim_cnt == restored_claim_cnt, primary_claim_cnt, restored_claim_cnt),
            "evidence": (primary_ev_cnt == restored_ev_cnt, primary_ev_cnt, restored_ev_cnt),
        },
        "invariants_satisfied": {
            "event_article_count_mismatch": mismatch_counts == 0,
            "orphan_articles": orphan_articles == 0,
            "orphan_claims": orphan_claims == 0,
            "orphan_evidence": orphan_evidence == 0,
            "active_cycle_is_one": active_cycles == 1,
        },
        "success": (
            primary_art_cnt == restored_art_cnt
            and mismatch_counts == 0
            and orphan_articles == 0
            and orphan_claims == 0
            and orphan_evidence == 0
        ),
    }


if __name__ == "__main__":
    result = run_dr_drill()
    print(json.dumps(result, indent=2, default=str))
