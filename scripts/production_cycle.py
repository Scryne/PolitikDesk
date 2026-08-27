"""PolitikDesk Üretim Veri Yaşam Döngüsü ve Döngü Yönetim Aracı (Faz 21).

Komut Satırı Arayüzü (CLI):
    python -m scripts.production_cycle status
    python -m scripts.production_cycle list
    python -m scripts.production_cycle create --name "Yeni Döngü" [--key KEY] [--dry-run] [--yes]
    python -m scripts.production_cycle archive-current [--dry-run] [--yes]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from typing import Any

from politikdesk.db import connection, fetch_one
from politikdesk.observability import get_logger

log = get_logger(__name__)

# Windows konsolunda UTF-8 / cp1254 kodlama hatalarını önle
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def get_active_cycle(conn: Any = None) -> dict[str, Any] | None:
    """Mevcut aktif üretim döngüsünü döner."""
    sql = """
        SELECT id, cycle_key, name, status, started_at, ended_at, created_at, meta
        FROM publication_cycles
        WHERE status = 'active'
        LIMIT 1
    """
    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return dict(row) if row else None

    with connection() as c, c.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        return dict(row) if row else None


def get_cycle_counts(cycle_id: int, conn: Any = None) -> dict[str, int]:
    """Belirli bir döngüye ait makale, olay, iddia ve kanıt sayılarını döner."""

    def _run(cur: Any) -> dict[str, int]:
        cur.execute("SELECT count(*) FROM articles WHERE cycle_id = %s", (cycle_id,))
        art_count = int(fetch_one(cur)["count"])

        cur.execute("SELECT count(*) FROM events WHERE cycle_id = %s", (cycle_id,))
        ev_count = int(fetch_one(cur)["count"])

        cur.execute(
            """
            SELECT count(*) FROM claims c
            JOIN events e ON e.id = c.event_id
            WHERE e.cycle_id = %s
            """,
            (cycle_id,),
        )
        clm_count = int(fetch_one(cur)["count"])

        cur.execute(
            """
            SELECT count(*) FROM evidence ev
            JOIN claims c ON c.id = ev.claim_id
            JOIN events e ON e.id = c.event_id
            WHERE e.cycle_id = %s
            """,
            (cycle_id,),
        )
        evi_count = int(fetch_one(cur)["count"])

        return {
            "articles": art_count,
            "events": ev_count,
            "claims": clm_count,
            "evidence": evi_count,
        }

    if conn is not None:
        with conn.cursor() as cur:
            return _run(cur)

    with connection() as c, c.cursor() as cur:
        return _run(cur)


def cmd_status() -> int:
    """Aktif ve arşiv döngülerinin durum raporunu görüntüler."""
    print("=" * 70)
    print("POLİTİKDESK PRODUCTION DATA LIFECYCLE STATUS")
    print("=" * 70)

    active = get_active_cycle()
    if active:
        counts = get_cycle_counts(active["id"])
        print(f"[*] AKTİF DÖNGÜ: #{active['id']} [{active['cycle_key']}]")
        print(f"    İsim:        {active['name']}")
        print(f"    Başlangıç:   {active['started_at']}")
        print("    Veri Sayıları (Aktif):")
        print(f"      - Makaleler: {counts['articles']:,}")
        print(f"      - Olaylar:   {counts['events']:,}")
        print(f"      - İddialar:  {counts['claims']:,}")
        print(f"      - Kanıtlar:  {counts['evidence']:,}")
    else:
        print("[!] UYARI: Sistemde şu an aktif bir üretim döngüsü bulunmuyor!")

    print("-" * 70)
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, cycle_key, name, status, started_at, ended_at
            FROM publication_cycles
            WHERE status <> 'active'
            ORDER BY started_at DESC
            """
        )
        archived_rows = cur.fetchall()

    print(f"ARŞİVLENMİŞ DÖNGÜLER ({len(archived_rows)} adet):")
    for row in archived_rows:
        c = get_cycle_counts(row["id"])
        print(
            f'  • #{row["id"]} [{row["cycle_key"]}] "{row["name"]}" '
            f"({row['started_at']} -> {row['ended_at']}) | "
            f"{c['articles']:,} makale, {c['events']:,} olay"
        )
    print("=" * 70)
    return 0


def cmd_list() -> int:
    """Tüm üretim döngülerini listeler."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, cycle_key, name, status, started_at, ended_at
            FROM publication_cycles
            ORDER BY id ASC
            """
        )
        rows = cur.fetchall()

    print(f"{'ID':<4} {'DURUM':<10} {'KEY':<24} {'BAŞLANGIÇ':<22} {'İSİM'}")
    print("-" * 80)
    for r in rows:
        st = r["status"].upper()
        s_at = str(r["started_at"])[:19] if r["started_at"] else "-"
        print(f"{r['id']:<4} {st:<10} {r['cycle_key']:<24} {s_at:<22} {r['name']}")
    return 0


def cmd_archive_current(*, dry_run: bool = False, yes: bool = False) -> int:
    """Mevcut aktif döngüyü arşivler."""
    active = get_active_cycle()
    if not active:
        print("[!] HATA: Arşivlenecek aktif döngü bulunamadı.")
        return 1

    print(f"[*] Mevcut aktif döngü arşivlenecek: #{active['id']} ({active['name']})")
    if dry_run:
        print("[DRY-RUN] Değişiklik yapılmadı.")
        return 0

    if not yes:
        confirm = input("Emin misiniz? [e/H]: ").strip().lower()
        if confirm not in ("e", "evet", "y", "yes"):
            print("İşlem iptal edildi.")
            return 1

    now = datetime.now(UTC)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE publication_cycles
                SET status = 'archived', ended_at = %s
                WHERE id = %s
                """,
                (now, active["id"]),
            )
            cur.execute(
                """
                INSERT INTO audit_log (actor, action, target, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (
                    "system:production_cycle_cli",
                    "archive_cycle",
                    f"publication_cycles:{active['id']}",
                    json.dumps(
                        {
                            "cycle_key": active["cycle_key"],
                            "name": active["name"],
                            "archived_at": now.isoformat(),
                        }
                    ),
                ),
            )
        conn.commit()

    print(f"[OK] Döngü #{active['id']} [{active['cycle_key']}] başarıyla arşivlendi.")
    return 0


def cmd_create(
    name: str,
    *,
    key: str | None = None,
    dry_run: bool = False,
    yes: bool = False,
) -> int:
    """Yeni bir aktif üretim döngüsü başlatır (önceki aktif döngüyü arşivler)."""
    now = datetime.now(UTC)
    cycle_key = key or f"prod_cycle_{now.strftime('%Y%m%d_%H%M%S')}"

    active = get_active_cycle()
    print("[*] Yeni Aktif Döngü Başlatılacak:")
    print(f"    Key:       {cycle_key}")
    print(f"    İsim:      {name}")
    if active:
        print(f"    Arşivlenecek Eski Döngü: #{active['id']} ({active['name']})")

    if dry_run:
        print("[DRY-RUN] Değişiklik yapılmadı.")
        return 0

    if not yes:
        confirm = input("Yeni döngüyü başlatmak istediğinize emin misiniz? [e/H]: ").strip().lower()
        if confirm not in ("e", "evet", "y", "yes"):
            print("İşlem iptal edildi.")
            return 1

    with connection() as conn:
        with conn.cursor() as cur:
            # 1. Eski aktif döngüyü arşivle
            if active:
                cur.execute(
                    """
                    UPDATE publication_cycles
                    SET status = 'archived', ended_at = %s
                    WHERE id = %s
                    """,
                    (now, active["id"]),
                )
                cur.execute(
                    """
                    INSERT INTO audit_log (actor, action, target, payload)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (
                        "system:production_cycle_cli",
                        "archive_cycle",
                        f"publication_cycles:{active['id']}",
                        json.dumps(
                            {
                                "cycle_key": active["cycle_key"],
                                "name": active["name"],
                                "archived_at": now.isoformat(),
                            }
                        ),
                    ),
                )

            # 2. Yeni aktif döngüyü ekle
            cur.execute(
                """
                INSERT INTO publication_cycles (cycle_key, name, status, started_at, meta)
                VALUES (%s, %s, 'active', %s, %s::jsonb)
                RETURNING id
                """,
                (
                    cycle_key,
                    name,
                    now,
                    json.dumps(
                        {
                            "created_by": "production_cycle_cli",
                            "created_at": now.isoformat(),
                        }
                    ),
                ),
            )
            new_id = int(fetch_one(cur)["id"])

            cur.execute(
                """
                INSERT INTO audit_log (actor, action, target, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (
                    "system:production_cycle_cli",
                    "create_active_cycle",
                    f"publication_cycles:{new_id}",
                    json.dumps(
                        {
                            "cycle_id": new_id,
                            "cycle_key": cycle_key,
                            "name": name,
                            "started_at": now.isoformat(),
                        }
                    ),
                ),
            )
        conn.commit()

    print(f'[OK] Yeni aktif üretim döngüsü oluşturuldu: #{new_id} [{cycle_key}] - "{name}"')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="production-cycle",
        description="PolitikDesk Üretim Veri Yaşam Döngüsü Yöneticisi (Faz 21)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    subparsers.add_parser("status", help="Aktif ve arşiv döngülerinin durumunu gösterir.")

    # list
    subparsers.add_parser("list", help="Tüm döngüleri listeler.")

    # archive-current
    p_arch = subparsers.add_parser("archive-current", help="Mevcut aktif döngüyü arşivler.")
    p_arch.add_argument(
        "--dry-run", action="store_true", help="Yalnızca simüle et, veritabanına yazma."
    )
    p_arch.add_argument("-y", "--yes", action="store_true", help="Onay sormadan çalıştır.")

    # create
    p_create = subparsers.add_parser("create", help="Yeni bir aktif üretim döngüsü oluşturur.")
    p_create.add_argument("--name", required=True, help="Döngü açıklaması/adı")
    p_create.add_argument("--key", help="Özel döngü anahtarı (varsayılan: otomatik tarih)")
    p_create.add_argument(
        "--dry-run", action="store_true", help="Yalnızca simüle et, veritabanına yazma."
    )
    p_create.add_argument("-y", "--yes", action="store_true", help="Onay sormadan çalıştır.")

    args = parser.parse_args(argv)

    if args.command == "status":
        return cmd_status()
    if args.command == "list":
        return cmd_list()
    if args.command == "archive-current":
        return cmd_archive_current(dry_run=args.dry_run, yes=args.yes)
    if args.command == "create":
        return cmd_create(name=args.name, key=args.key, dry_run=args.dry_run, yes=args.yes)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
