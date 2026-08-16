"""Beklenen gelişme ↔ gerçekleşen olay eşleştirmesi (F2-18, F2-19).

DoD (F2-19): Takvimde 14:30 TÜİK kaydı varsa, o saatte gelen TÜİK olayı
otomatik `linked_event_id` alıyor.

Spec §9.5 bunu "MVP'nin gizli kozu" olarak tanımlar: ürün yalnızca olanı
değil, **olacağı** da bilir. TÜİK veri takvimi ve TCMB PPK tarihleri
önceden yayımlanır; bunları beklemek, haberi rakiplerden önce
bağlamlandırmayı mümkün kılar.

## Eşleştirme kuralı

Bir `scheduled_events` kaydı ile bir olay eşleşir eğer:

  1. **Zaman**: olayın ilk bildirimi, beklenen zamanın ± penceresinde
  2. **Kaynak**: olayın makalelerinden biri takvimdeki kurumdan geliyor
     (ya da takvim kaydında kaynak belirtilmemiş)
  3. **Dikey**: aynı dikey

Kaynak koşulu zorunludur: aynı saatte başka bir olay da gelebilir. Yalnız
zamana bakan bir eşleştirme, TÜİK enflasyon açıklamasına o saatte çıkan
alakasız bir haberi bağlardı.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from politikdesk.db import connection, fetch_one
from politikdesk.observability import get_logger

log = get_logger(__name__)

# Kurumlar yayın saatini tutturur ama gecikme olur; haber akışı da
# birkaç dakika sonra gelir. 3 saat, aynı gün içinde başka bir yayınla
# karışmayacak kadar dar, gecikmeyi tolere edecek kadar geniştir.
MATCH_WINDOW = timedelta(hours=3)


@dataclass(frozen=True)
class ScheduledEvent:
    id: int
    title: str
    expected_at: Any
    source_slug: str | None
    vertical: str
    status: str
    linked_event_id: int | None


def list_scheduled(*, upcoming_only: bool = False, limit: int = 100) -> list[dict[str, Any]]:
    """Takvim kayıtları (F2-18 admin ekranının veri kaynağı)."""
    where = "WHERE se.expected_at > now()" if upcoming_only else ""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT se.id, se.title, se.expected_at, se.vertical, se.status,
                   se.linked_event_id, s.slug AS source_slug,
                   e.title AS linked_event_title
            FROM scheduled_events se
            LEFT JOIN sources s ON s.id = se.source_id
            LEFT JOIN events e ON e.id = se.linked_event_id
            {where}
            ORDER BY se.expected_at
            LIMIT %s
            """,  # noqa: S608 — `where` sabit iki değerden biri
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


def add_scheduled(
    *,
    title: str,
    expected_at: Any,
    source_slug: str | None = None,
    vertical: str = "macro_economy",
) -> int:
    """Takvime elle giriş (F2-18)."""
    with connection() as conn, conn.cursor() as cur:
        source_id = None
        if source_slug:
            cur.execute("SELECT id FROM sources WHERE slug = %s", (source_slug,))
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"Kaynak bulunamadı: {source_slug}")
            source_id = row["id"]

        cur.execute(
            """
            INSERT INTO scheduled_events (title, expected_at, source_id, vertical)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            (title, expected_at, source_id, vertical),
        )
        scheduled_id = fetch_one(cur)["id"]
        conn.commit()

    log.info("scheduled_event_added", id=scheduled_id, title=title)
    return scheduled_id


def match_pending(window: timedelta = MATCH_WINDOW) -> dict[str, int]:
    """Beklenen gelişmeleri gerçekleşen olaylarla eşleştirir (F2-19).

    Yalnızca `status='pending'` kayıtlar denenir; eşleşen kayıt
    `occurred` olur ve `linked_event_id` alır.
    """
    matched = 0
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT se.id, se.expected_at, se.vertical, se.source_id
            FROM scheduled_events se
            WHERE se.status = 'pending'
              AND se.linked_event_id IS NULL
              AND se.expected_at < now()
            ORDER BY se.expected_at
            """
        )
        pending = [dict(r) for r in cur.fetchall()]

        for item in pending:
            cur.execute(
                """
                SELECT e.id,
                       abs(extract(epoch FROM e.first_reported_at - %s)) AS delta
                FROM events e
                WHERE e.merged_into_id IS NULL
                  AND e.vertical = %s
                  AND e.first_reported_at BETWEEN %s - %s AND %s + %s
                  AND (
                    %s IS NULL
                    OR EXISTS (
                      SELECT 1 FROM articles a
                      WHERE a.event_id = e.id AND a.source_id = %s
                    )
                  )
                ORDER BY delta
                LIMIT 1
                """,
                (
                    item["expected_at"],
                    item["vertical"],
                    item["expected_at"],
                    window,
                    item["expected_at"],
                    window,
                    item["source_id"],
                    item["source_id"],
                ),
            )
            hit = cur.fetchone()
            if hit is None:
                from datetime import UTC, datetime
                expected = item["expected_at"]
                if expected.tzinfo is None:
                    expected = expected.replace(tzinfo=UTC)
                if datetime.now(UTC) - expected > timedelta(hours=48):
                    cur.execute(
                        "UPDATE scheduled_events SET status = 'cancelled' WHERE id = %s",
                        (item["id"],),
                    )
                continue

            cur.execute(
                """
                UPDATE scheduled_events
                SET linked_event_id = %s, status = 'occurred'
                WHERE id = %s
                """,
                (hit["id"], item["id"]),
            )
            matched += 1
            log.info(
                "scheduled_event_matched",
                scheduled_id=item["id"],
                event_id=hit["id"],
                delta_seconds=int(hit["delta"]),
            )
        conn.commit()

    stats = {"pending": len(pending), "matched": matched}
    log.info("scheduler_match_complete", **stats)
    return stats
