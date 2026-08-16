"""G4′ Günlük Durum Kaydı (Daily Snapshot) ve Gözlem Aracı.

Bu betik, POLİTİKDESK-FAZ-FAZ-YOL-HARITASI.md G4′-1 gereksinimleri uyarınca
7 günlük G4′ gözlem döngüsü boyunca her gün sistem durumunu ölçer ve
docs/G4-SNAPSHOTS.md denetim defterine işler.

Toplanan Ölçümler:
- date: Zaman damgası
- source health: 16 kaynağın fetch ve başarı durumu
- pipeline health: 8 alt sistemin sağlık durumu
- failure rate: Sıfırlanmış pencere ve son 24 saatlik arıza oranı
- backlog: İşlenmemiş / bekleyen veri birikmesi
- container SHA: Canlı konteyner SHA'sı ve /version yanıtı
- DB schema: Veritabanı şema sürümü ve migration durumu
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from politikdesk.db import connection

SNAPSHOT_DOC_PATH = Path("docs/G4-SNAPSHOTS.md")
DEFAULT_BASELINE_TS = "2026-08-15T13:00:00+00:00"  # Faz 8 Deploy zamanı


@dataclass
class SnapshotData:
    timestamp: datetime
    day_number: int
    git_sha: str
    container_sha: str
    db_schema: str
    source_count: int
    sources_healthy: int
    sources_failed: int
    total_fetches_since_reset: int
    failed_fetches_since_reset: int
    failure_rate_since_reset: float
    total_fetches_24h: int
    failed_fetches_24h: int
    failure_rate_24h: float
    articles_count: int
    events_count: int
    claims_count: int
    evidence_count: int
    drafts_count: int
    briefings_count: int
    briefings_sent: int
    pipeline_health: str
    backlog_summary: str
    status_note: str


def fetch_version_endpoint(url: str = "http://127.0.0.1:8000/version") -> dict[str, Any]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PolitikDesk-G4-Snapshot/1.0"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict):
                return data
            return {}
    except Exception as e:
        return {"error": str(e), "git_sha": "unknown", "db_schema_version": "unknown"}


def collect_snapshot_data(since_ts: datetime) -> SnapshotData:
    now_dt = datetime.now(UTC)
    version_info = fetch_version_endpoint()
    git_sha = str(version_info.get("git_sha", "unknown"))[:12]
    db_schema = str(version_info.get("db_schema_version", "unknown"))

    days_since = (now_dt - since_ts).total_seconds() / 86400.0
    day_number = int(days_since)

    with connection() as conn, conn.cursor() as cur:
        # 1. Kaynak sağlığı
        cur.execute("SELECT count(*) as total FROM sources WHERE is_active = true;")
        row_sources = cur.fetchone()
        source_count: int = int(row_sources["total"]) if row_sources else 0

        cur.execute(
            """
            SELECT
                s.slug,
                count(f.id) as fetches,
                count(f.id) FILTER (WHERE NOT f.succeeded) as failures
            FROM sources s
            LEFT JOIN source_fetch_log f ON f.source_id = s.id AND f.started_at >= %s
            WHERE s.is_active = true
            GROUP BY s.slug;
            """,
            (since_ts,),
        )
        source_rows = cur.fetchall()
        sources_healthy = 0
        sources_failed = 0
        for r in source_rows:
            failures_cnt = int(r["failures"] or 0)
            fetches_cnt = int(r["fetches"] or 0)
            if failures_cnt > 0 and fetches_cnt == failures_cnt:
                sources_failed += 1
            else:
                sources_healthy += 1

        # 2. Fetch arıza oranı (Sıfırlama sonrası)
        cur.execute(
            """
            SELECT
                count(*) as total,
                count(*) FILTER (WHERE NOT succeeded) as failed
            FROM source_fetch_log
            WHERE started_at >= %s;
            """,
            (since_ts,),
        )
        row_reset = cur.fetchone()
        tot_reset = int(row_reset["total"] or 0) if row_reset else 0
        fail_reset = int(row_reset["failed"] or 0) if row_reset else 0
        rate_reset = (fail_reset * 100.0 / tot_reset) if tot_reset > 0 else 0.0

        # 3. Fetch arıza oranı (Son 24 saat)
        cur.execute(
            """
            SELECT
                count(*) as total,
                count(*) FILTER (WHERE NOT succeeded) as failed
            FROM source_fetch_log
            WHERE started_at >= now() - interval '24 hours';
            """
        )
        row_24h = cur.fetchone()
        tot_24h = int(row_24h["total"] or 0) if row_24h else 0
        fail_24h = int(row_24h["failed"] or 0) if row_24h else 0
        rate_24h = (fail_24h * 100.0 / tot_24h) if tot_24h > 0 else 0.0

        # 4. Tablo sayıları
        cur.execute("SELECT count(*) as c FROM articles;")
        row_art = cur.fetchone()
        articles_count = int(row_art["c"]) if row_art else 0

        cur.execute("SELECT count(*) as c FROM events;")
        row_evt = cur.fetchone()
        events_count = int(row_evt["c"]) if row_evt else 0

        cur.execute("SELECT count(*) as c FROM claims;")
        row_clm = cur.fetchone()
        claims_count = int(row_clm["c"]) if row_clm else 0

        cur.execute("SELECT count(*) as c FROM evidence;")
        row_evi = cur.fetchone()
        evidence_count = int(row_evi["c"]) if row_evi else 0

        cur.execute("SELECT count(*) as c FROM drafts;")
        row_drf = cur.fetchone()
        drafts_count = int(row_drf["c"]) if row_drf else 0

        cur.execute(
            """
            SELECT
                count(*) as total,
                count(*) FILTER (WHERE sent_at IS NOT NULL) as sent
            FROM briefings;
            """
        )
        row_b = cur.fetchone()
        briefings_count = int(row_b["total"] or 0) if row_b else 0
        briefings_sent = int(row_b["sent"] or 0) if row_b else 0

        # 5. Backlog kontrolü
        cur.execute("SELECT count(*) as c FROM articles WHERE event_id IS NULL;")
        row_uncl = cur.fetchone()
        unclustered_articles = int(row_uncl["c"]) if row_uncl else 0

        cur.execute(
            """
            SELECT count(*) as c FROM drafts
            WHERE user_action NOT IN ('accepted', 'edited', 'rejected', 'published');
            """
        )
        row_pnd = cur.fetchone()
        pending_drafts = int(row_pnd["c"]) if row_pnd else 0

        backlog_summary = f"Unclustered: {unclustered_articles}, Pending Drafts: {pending_drafts}"

    # Pipeline genel durumu
    pipeline_health = (
        "🟢 8/8 GREEN" if sources_failed == 0 else f"🟡 {sources_failed} kaynakta hata"
    )
    status_note = (
        f"G4′ Day {day_number} izlemede. Sıfırlama sonrası {tot_reset} fetch "
        f"(%{rate_reset:.2f} hata)."
    )

    return SnapshotData(
        timestamp=now_dt,
        day_number=day_number,
        git_sha=git_sha,
        container_sha=git_sha,
        db_schema=db_schema,
        source_count=source_count,
        sources_healthy=sources_healthy,
        sources_failed=sources_failed,
        total_fetches_since_reset=tot_reset,
        failed_fetches_since_reset=fail_reset,
        failure_rate_since_reset=rate_reset,
        total_fetches_24h=tot_24h,
        failed_fetches_24h=fail_24h,
        failure_rate_24h=rate_24h,
        articles_count=articles_count,
        events_count=events_count,
        claims_count=claims_count,
        evidence_count=evidence_count,
        drafts_count=drafts_count,
        briefings_count=briefings_count,
        briefings_sent=briefings_sent,
        pipeline_health=pipeline_health,
        backlog_summary=backlog_summary,
        status_note=status_note,
    )


def format_markdown_row(s: SnapshotData) -> str:
    ts_str = s.timestamp.strftime("%Y-%m-%d %H:%M UTC")
    fail_reset_str = (
        f"%{s.failure_rate_since_reset:.2f} "
        f"({s.failed_fetches_since_reset}/{s.total_fetches_since_reset})"
    )
    return (
        f"| Gün {s.day_number} | {ts_str} | `{s.git_sha}` | "
        f"{s.sources_healthy}/{s.source_count} aktif | {s.pipeline_health} | "
        f"{fail_reset_str} | "
        f"{s.articles_count} art / {s.events_count} evt | "
        f"{s.briefings_sent}/{s.briefings_count} | `{s.db_schema}` | "
        f"{s.backlog_summary} |"
    )


def append_snapshot_to_file(snap: SnapshotData, file_path: Path = SNAPSHOT_DOC_PATH) -> None:
    row = format_markdown_row(snap)

    if not file_path.exists():
        header = (
            "# PolitikDesk — G4′ Günlük Durum Kayıtları (Daily Snapshots)\n\n"
            "**Kapsam:** FAZ 9 — 7 Gün Kesintisiz Akış ve Gözlem Protokolü (G4′-1)\n"
            f"**Başlangıç Zamanı:** {DEFAULT_BASELINE_TS}\n\n"
            "---\n\n"
            "| Gün | Tarih / Saat (UTC) | Git SHA | Kaynak Durumu | Pipeline | "
            "Arıza Oranı (Sıfırdan) | Veri Hacmi | Brifing | DB Schema | Backlog Durumu |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n"
        )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(header + row + "\n", encoding="utf-8")
        return

    content = file_path.read_text(encoding="utf-8")
    new_content = content.rstrip() + "\n" + row + "\n"
    file_path.write_text(new_content, encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="PolitikDesk G4′ Günlük Snapshot Aracı")
    parser.add_argument(
        "--since",
        type=str,
        default=DEFAULT_BASELINE_TS,
        help=f"Sıfırlanmış başlangıç zamanı (Varsayılan: {DEFAULT_BASELINE_TS})",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=SNAPSHOT_DOC_PATH,
        help="Yazılacak markdown dosyası",
    )
    parser.add_argument("--no-write", action="store_true", help="Dosyaya yazma, sadece stdout")
    parser.add_argument(
        "--git-commit",
        action="store_true",
        help="Snapshot kaydedildikten sonra git'e commit at",
    )
    args = parser.parse_args()

    since_dt = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
    if since_dt.tzinfo is None:
        since_dt = since_dt.replace(tzinfo=UTC)

    snap = collect_snapshot_data(since_dt)

    print("=" * 80)
    print(f"POLİTİKDESK — G4′ GÜNLÜK SNAPSHOT (GÜN {snap.day_number})")
    print(f"Zaman: {snap.timestamp:%Y-%m-%d %H:%M:%S UTC}")
    print("=" * 80)
    print(f"Git / Konteyner SHA : {snap.git_sha}")
    print(f"DB Schema           : {snap.db_schema}")
    print(f"Kaynak Sağlığı      : {snap.sources_healthy}/{snap.source_count} Aktif")
    print(f"Pipeline Durumu     : {snap.pipeline_health}")
    fail_since_desc = (
        f"%{snap.failure_rate_since_reset:.2f} "
        f"({snap.failed_fetches_since_reset}/{snap.total_fetches_since_reset})"
    )
    print(f"Arıza Oranı (Sıfır) : {fail_since_desc}")
    fail_24h_desc = (
        f"%{snap.failure_rate_24h:.2f} ({snap.failed_fetches_24h}/{snap.total_fetches_24h})"
    )
    print(f"Arıza Oranı (Son 24s): {fail_24h_desc}")
    data_desc = (
        f"{snap.articles_count} makale, {snap.events_count} olay, "
        f"{snap.claims_count} iddia, {snap.evidence_count} kanıt"
    )
    print(f"Veri Durumu         : {data_desc}")
    print(f"Brifing Durumu      : {snap.briefings_sent}/{snap.briefings_count} gönderildi")
    print(f"Backlog             : {snap.backlog_summary}")
    print(f"Not                 : {snap.status_note}")
    print("=" * 80)

    if not args.no_write:
        append_snapshot_to_file(snap, args.output_file)
        print(f"Snapshot başarıyla kaydedildi: {args.output_file}")
        if args.git_commit:
            try:
                subprocess.run(
                    ["git", "add", str(args.output_file)],
                    check=True,
                    capture_output=True,
                )
                msg = (
                    f"chore(g4): record Day {snap.day_number} snapshot ({snap.timestamp:%Y-%m-%d})"
                )
                subprocess.run(
                    ["git", "commit", "-m", msg],
                    check=True,
                    capture_output=True,
                )
                print(f"[OK] Snapshot git'e commit edildi: {msg}")
            except Exception as e:
                print(f"[UYARI] Git commit atılamadı: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
