"""Correction Rate ve Olay İnceleme Takipçisi (AŞAMA 4 · G4′-3 · Madde 4).

Kullanıcının 34 olaylık manuel inceleme sürecini (günlük ~5 olay) ve
editoryal düzeltme/itiraz oranını (hedef: ≤ %3) ölçer ve detaylı raporlar.

Kullanım:
    python -m scripts.correction_report
    python -m scripts.correction_report --since 2026-08-15
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from datetime import UTC, datetime
from typing import Any

from politikdesk.config import get_settings, load_env_file
from politikdesk.db import connection

# Windows konsolunda UTF-8 kodlama
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def get_correction_stats(cur: Any, since: datetime | None = None) -> dict[str, Any]:
    """İncelenen olayları ve geri bildirimleri sorgular."""
    query = """
        WITH opened AS (
            SELECT ua.event_id,
                   min(ua.occurred_at) AS first_opened_at,
                   count(*) AS open_count
            FROM user_activity ua
            WHERE ua.kind = 'event_open' AND ua.event_id IS NOT NULL
                  {since_filter}
            GROUP BY ua.event_id
        )
        SELECT
            o.event_id,
            e.title,
            e.topic_tags,
            e.vertical,
            o.first_opened_at,
            o.open_count,
            ef.id AS feedback_id,
            ef.note AS feedback_note,
            ef.scope AS feedback_scope,
            ef.created_at AS feedback_at
        FROM opened o
        JOIN events e ON e.id = o.event_id
        LEFT JOIN event_feedback ef ON ef.event_id = o.event_id
        ORDER BY o.first_opened_at DESC;
    """
    since_filter = "AND ua.occurred_at >= %s" if since else ""
    formatted_query = query.format(since_filter=since_filter)

    params = (since,) if since else ()
    cur.execute(formatted_query, params)
    rows = cur.fetchall()

    opened_events: dict[int, dict[str, Any]] = {}
    for r in rows:
        eid = r["event_id"]
        if eid not in opened_events:
            opened_events[eid] = {
                "event_id": eid,
                "title": r["title"],
                "topic_tags": r["topic_tags"],
                "vertical": r["vertical"],
                "first_opened_at": r["first_opened_at"],
                "open_count": r["open_count"],
                "feedbacks": [],
            }
        if r["feedback_id"] is not None:
            opened_events[eid]["feedbacks"].append(
                {
                    "feedback_id": r["feedback_id"],
                    "note": r["feedback_note"],
                    "scope": r["feedback_scope"],
                    "created_at": r["feedback_at"],
                }
            )

    total_opened = len(opened_events)
    events_with_feedback = sum(1 for e in opened_events.values() if len(e["feedbacks"]) > 0)
    correction_rate = (events_with_feedback * 100.0 / total_opened) if total_opened > 0 else 0.0

    return {
        "total_opened": total_opened,
        "events_with_feedback": events_with_feedback,
        "correction_rate": correction_rate,
        "events": list(opened_events.values()),
    }


def print_report(stats: dict[str, Any], target_sample: int = 34, target_rate: float = 3.0) -> None:
    total_opened = stats["total_opened"]
    events_with_feedback = stats["events_with_feedback"]
    rate = stats["correction_rate"]
    remaining = max(0, target_sample - total_opened)

    print("=" * 70)
    print("POLITIKDESK — CORRECTION RATE & OLAY INCELEME RAPORU (G4′-3)")
    print("=" * 70)
    print(f"Rapor Zamani: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()

    print(f"Hedef Örneklem Büyüklüğü: >= {target_sample} incelenmiş olay")
    print(f"Mevcut İncelenen Olay   : {total_opened} / {target_sample} (Kalan: {remaining})")
    print(f"Editoryal İtiraz / Hata : {events_with_feedback}")
    print(f"Mevcut Düzeltme Oranı   : %{rate:.2f} (Hedef: <= %{target_rate:.1f})")
    print()

    # Kapı durumu
    if total_opened < target_sample:
        status_msg = (
            f"🟡 DEVAM EDİYOR — İstatistiki geçerlilik için en az {target_sample} "
            f"olay incelenmeli ({total_opened}/{target_sample})"
        )
    elif rate <= target_rate:
        status_msg = (
            f"🟢 PASS — Örneklem ({total_opened} >= {target_sample}) ve "
            f"oran (%{rate:.2f} <= %{target_rate:.1f}) sağlandı."
        )
    else:
        status_msg = f"🔴 FAIL — Düzeltme oranı hedefi aşıyor (%{rate:.2f} > %{target_rate:.1f})."

    print(f"KAPI DURUMU: {status_msg}")
    print("-" * 70)

    # Detay listesi
    if stats["events"]:
        print("\nSon İncelenen Olaylar:")
        for ev in stats["events"][:15]:
            has_fb = len(ev["feedbacks"]) > 0
            flag = "🔴 DÜZELTME" if has_fb else "🟢 ONAYLI"
            opened_at = ev["first_opened_at"]
            opened_str = opened_at.strftime("%d.%m %H:%M") if opened_at else "—"
            print(f"  [{flag}] #{ev['event_id']:<4} | {opened_str} | {ev['title'][:45]}")
            for fb in ev["feedbacks"]:
                print(f"          ↳ Not: {fb['note']} (kapsam: {fb['scope']})")
    else:
        print("\nHenüz incelenmiş olay kaydı bulunmuyor.")

    print("\n" + "=" * 70)
    if total_opened < target_sample:
        daily_target = 5
        days_left = (remaining + daily_target - 1) // daily_target
        print(
            f"💡 Tavsiye: Günlük ~{daily_target} olay inceleyerek ~{days_left} "
            f"gün içinde {target_sample} hedefine ulaşabilirsiniz."
        )
        print("   Feed: http://localhost:8000/feed")
    print("=" * 70)


def main() -> int:
    load_env_file()
    parser = argparse.ArgumentParser(description="PolitikDesk Correction Rate Takipçisi")
    parser.add_argument(
        "--since",
        type=str,
        default="2026-08-15T13:00:00+00:00",
        help="Ölçüm başlangıç zamanı (varsayılan: G4′ sıfırlama anı)",
    )
    parser.add_argument("--all", action="store_true", help="Tüm zamanları dahil et")
    args = parser.parse_args()

    since_dt = None
    if not args.all and args.since:
        with contextlib.suppress(ValueError):
            since_dt = datetime.fromisoformat(args.since)

    settings = get_settings()
    if not settings.database_url:
        print("HATA: PD_DATABASE_URL ayarlanmamış.", file=sys.stderr)
        return 1

    with connection() as conn, conn.cursor() as cur:
        stats = get_correction_stats(cur, since=since_dt)
        print_report(stats)

    return 0


if __name__ == "__main__":
    sys.exit(main())
