"""Merge / split kaçış valfleri (F2-05).

DoD: İki olay birleştirilebiliyor (`merged_into_id`), bir olay
bölünebiliyor; her işlem `audit_log`'da; geri alınabiliyor.

**Neden bu modül pazarlıksız.** Spec §11.4: "Kümeleme algoritması
mükemmel olmayacak; zorunlu kaçış valfleri" ve G2 koşul 8: merge/split
**%100** geri alınabilir. Kümeleme hatasının veri kaybına dönüşmemesi,
otomatik kümelemeye güvenilebilmesinin ön koşuludur.

**Geri alınabilirliği ne sağlıyor:**

1. `merged_into_id` — birleştirilen olay SİLİNMEZ, işaretlenir. Üyeleri
   hedefe taşınır ama kaynak kayıt (başlık, ilk görülme zamanı, merkez)
   durur.
2. `centroid.remove_member()` — merkez tam ortalama olduğu için üye
   çıkarma kayıpsızdır (bkz. `centroid.py`).
3. `audit_log` — her işlem, geri almak için gereken **tam bilgiyle**
   yazılır: hangi makaleler taşındı, hedef ve kaynak neydi. Kayıt
   yetersizse işlem geri alınamaz; bu yüzden `payload` makale
   kimliklerini içerir.

**Tasarım kısıtı:** merkez, taşınan üyelerden **yeniden hesaplanır**,
artımlı olarak düzeltilmez. Artımlı düzeltme birkaç merge/split
turundan sonra kayan nokta birikimi biriktirir; yeniden hesaplama
`centroid = mean(members)` özdeşliğini her işlemden sonra tazeler.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from politikdesk import audit
from politikdesk.clustering.centroid import recompute
from politikdesk.db import connection, fetch_one
from politikdesk.nlp.embedder import to_pgvector
from politikdesk.observability import get_logger

log = get_logger(__name__)

MERGER_VERSION = "merger@1.0.0"


class MergeError(RuntimeError):
    """Birleştirme/bölme kuralı ihlali."""


@dataclass(frozen=True)
class MergeResult:
    source_event_id: int
    target_event_id: int
    moved_article_ids: tuple[int, ...]
    moved_claim_ids: tuple[int, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_event_id": self.source_event_id,
            "target_event_id": self.target_event_id,
            "moved_article_ids": list(self.moved_article_ids),
            "moved_claim_ids": list(self.moved_claim_ids),
        }


@dataclass(frozen=True)
class SplitResult:
    source_event_id: int
    new_event_id: int
    moved_article_ids: tuple[int, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_event_id": self.source_event_id,
            "new_event_id": self.new_event_id,
            "moved_article_ids": list(self.moved_article_ids),
        }


# --------------------------------------------------------------- yardımcılar
def _vectors_of(cur: Any, event_id: int) -> list[list[float]]:
    cur.execute(
        """
        SELECT embedding::text AS embedding FROM articles
        WHERE event_id = %s AND embedding IS NOT NULL
        """,
        (event_id,),
    )
    return [[float(x) for x in r["embedding"].strip("[]").split(",") if x] for r in cur.fetchall()]


def _refresh_event(cur: Any, event_id: int) -> None:
    """Olayın merkezini, sayımını ve zamanlarını üyelerinden yeniden kurar.

    Üyesi kalmamışsa merkez NULL yapılır — sıfır vektör "her şeye eşit
    uzak" bir merkez üretir ve sonraki kümelemeyi sessizce bozar.
    """
    vectors = _vectors_of(cur, event_id)
    centroid = recompute(vectors)

    cur.execute(
        """
        UPDATE events e SET
          centroid_embedding = %s::vector,
          article_count      = COALESCE(sub.cnt, 0),
          first_reported_at  = COALESCE(sub.first_at, e.first_reported_at),
          last_update_at     = COALESCE(sub.last_at, e.last_update_at)
        FROM (
          SELECT count(*) AS cnt,
                 min(COALESCE(published_at, first_seen_at)) AS first_at,
                 max(COALESCE(published_at, first_seen_at)) AS last_at
          FROM articles WHERE event_id = %s
        ) sub
        WHERE e.id = %s
        """,
        (to_pgvector(centroid) if centroid else None, event_id, event_id),
    )

    # Varlık kümesi de üyelerden yeniden kurulmalı: taşınan makalelerin
    # varlıkları kaynakta kalırsa, sonraki kümelemede olmayan bir bağ
    # üzerinden eşleşme olur.
    cur.execute("DELETE FROM event_entities WHERE event_id = %s", (event_id,))
    cur.execute(
        """
        INSERT INTO event_entities (event_id, entity_id, role)
        SELECT DISTINCT %s, ae.entity_id, 'mentioned'
        FROM article_entities ae
        JOIN articles a ON a.id = ae.article_id
        WHERE a.event_id = %s
        ON CONFLICT DO NOTHING
        """,
        (event_id, event_id),
    )


# D06 düzeltmesi: yerel _audit kaldırıldı. Tüm çağrılar merkezî
# audit.write() üzerinden yapılır — eylem doğrulaması ve biçim
# tutarlılığı tek noktada sağlanır.


# ---------------------------------------------------------------- merge
def merge_events(source_event_id: int, target_event_id: int) -> MergeResult:
    """`source` olayını `target` içine birleştirir.

    Kaynak olay silinmez; `merged_into_id` ile işaretlenir ve makaleleri
    hedefe taşınır. `undo_merge` bunu tersine çevirebilir.
    """
    if source_event_id == target_event_id:
        raise MergeError("Bir olay kendisiyle birleştirilemez.")

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, vertical, merged_into_id FROM events WHERE id = ANY(%s) FOR UPDATE",
            ([source_event_id, target_event_id],),
        )
        found = {r["id"]: r for r in cur.fetchall()}
        for event_id in (source_event_id, target_event_id):
            if event_id not in found:
                raise MergeError(f"Olay bulunamadı: {event_id}")
        if found[target_event_id]["merged_into_id"] is not None:
            raise MergeError(
                f"Hedef olay ({target_event_id}) zaten başka bir olaya birleştirilmiş."
            )
        if found[source_event_id]["merged_into_id"] is not None:
            raise MergeError(f"Kaynak olay ({source_event_id}) zaten birleştirilmiş.")
        if found[source_event_id]["vertical"] != found[target_event_id]["vertical"]:
            raise MergeError(
                f"Farklı dikeylerdeki olaylar birleştirilemez: "
                f"kaynak={found[source_event_id]['vertical']!r}, "
                f"hedef={found[target_event_id]['vertical']!r}"
            )

        cur.execute("SELECT id FROM articles WHERE event_id = %s ORDER BY id", (source_event_id,))
        moved = tuple(r["id"] for r in cur.fetchall())

        cur.execute("SELECT id FROM claims WHERE event_id = %s ORDER BY id", (source_event_id,))
        moved_claims = tuple(r["id"] for r in cur.fetchall())

        cur.execute(
            "UPDATE articles SET event_id = %s WHERE event_id = %s",
            (target_event_id, source_event_id),
        )
        if moved_claims:
            cur.execute(
                "UPDATE claims SET event_id = %s WHERE event_id = %s",
                (target_event_id, source_event_id),
            )
        cur.execute(
            "UPDATE events SET merged_into_id = %s, review_flag = 'verified' WHERE id = %s",
            (target_event_id, source_event_id),
        )
        _refresh_event(cur, target_event_id)
        _refresh_event(cur, source_event_id)

        result = MergeResult(source_event_id, target_event_id, moved, moved_claim_ids=moved_claims)
        audit.write(
            "merge_events",
            f"events/{target_event_id}",
            actor="user:admin",
            payload=result.as_dict(),
            cursor=cur,
        )
        conn.commit()

    log.info("events_merged", **result.as_dict())
    return result


def undo_merge(source_event_id: int) -> MergeResult:
    """Birleştirmeyi geri alır (G2 koşul 8).

    Hangi makalelerin ve iddiaların taşındığı `audit_log`'dan okunur — bu yüzden merge
    kaydı makale ve iddia kimliklerini içermek zorundadır.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT merged_into_id FROM events WHERE id = %s FOR UPDATE",
            (source_event_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise MergeError(f"Olay bulunamadı: {source_event_id}")
        target_event_id = row["merged_into_id"]
        if target_event_id is None:
            raise MergeError(f"Olay ({source_event_id}) birleştirilmemiş.")

        cur.execute(
            """
            SELECT payload FROM audit_log
            WHERE action = 'merge_events'
              AND payload->>'source_event_id' = %s
            ORDER BY id DESC LIMIT 1
            """,
            (str(source_event_id),),
        )
        record = cur.fetchone()
        if record is None:
            raise MergeError(
                f"Birleştirme kaydı bulunamadı (events/{source_event_id}); geri alma yapılamaz."
            )
        moved = tuple(record["payload"].get("moved_article_ids", []))
        moved_claims = tuple(record["payload"].get("moved_claim_ids", []))

        if moved:
            cur.execute(
                "UPDATE articles SET event_id = %s WHERE id = ANY(%s)",
                (source_event_id, list(moved)),
            )
        if moved_claims:
            cur.execute(
                "UPDATE claims SET event_id = %s WHERE id = ANY(%s)",
                (source_event_id, list(moved_claims)),
            )
        cur.execute("UPDATE events SET merged_into_id = NULL WHERE id = %s", (source_event_id,))
        _refresh_event(cur, source_event_id)
        _refresh_event(cur, target_event_id)

        result = MergeResult(source_event_id, target_event_id, moved, moved_claim_ids=moved_claims)
        audit.write(
            "undo_merge",
            f"events/{source_event_id}",
            actor="user:admin",
            payload=result.as_dict(),
            cursor=cur,
        )
        conn.commit()

    log.info("merge_undone", **result.as_dict())
    return result


# ---------------------------------------------------------------- split
def split_event(source_event_id: int, article_ids: list[int]) -> SplitResult:
    """Verilen makaleleri kaynak olaydan alıp YENİ bir olaya taşır.

    Yeni olayın başlığı taşınan ilk makaleden gelir; kullanıcı admin
    ekranından düzeltebilir.
    """
    if not article_ids:
        raise MergeError("Bölme için en az bir makale gerekir.")

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, vertical, merged_into_id FROM events WHERE id = %s FOR UPDATE",
            (source_event_id,),
        )
        event = cur.fetchone()
        if event is None:
            raise MergeError(f"Olay bulunamadı: {source_event_id}")
        if event["merged_into_id"] is not None:
            raise MergeError("Birleştirilmiş bir olay bölünemez; önce geri alın.")

        cur.execute(
            """
            SELECT id, title, excerpt, COALESCE(published_at, first_seen_at) AS at
            FROM articles WHERE id = ANY(%s) AND event_id = %s ORDER BY at, id
            """,
            (article_ids, source_event_id),
        )
        rows = cur.fetchall()
        if len(rows) != len(set(article_ids)):
            raise MergeError("Makalelerin bir kısmı bu olaya ait değil; bölme yapılmadı.")

        cur.execute("SELECT count(*) AS n FROM articles WHERE event_id = %s", (source_event_id,))
        if fetch_one(cur)["n"] == len(rows):
            raise MergeError("Bir olayın TÜM makaleleri bölünemez — sonuç boş bir olay olurdu.")

        seed = rows[0]
        cur.execute(
            """
            INSERT INTO events (title, summary, vertical, first_reported_at,
                                last_update_at, review_flag)
            VALUES (%s, %s, %s, %s, %s, 'needs_review')
            RETURNING id
            """,
            (seed["title"], seed["excerpt"], event["vertical"], seed["at"], seed["at"]),
        )
        new_event_id = fetch_one(cur)["id"]

        moved = tuple(r["id"] for r in rows)
        cur.execute(
            "UPDATE articles SET event_id = %s WHERE id = ANY(%s)",
            (new_event_id, list(moved)),
        )
        _refresh_event(cur, new_event_id)
        _refresh_event(cur, source_event_id)

        result = SplitResult(source_event_id, new_event_id, moved)
        audit.write(
            "split_event",
            f"events/{source_event_id}",
            actor="user:admin",
            payload=result.as_dict(),
            cursor=cur,
        )
        conn.commit()

    log.info("event_split", **result.as_dict())
    return result


def undo_split(new_event_id: int) -> SplitResult:
    """Bölmeyi geri alır: yeni olayın makaleleri kaynağa döner."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT payload FROM audit_log
            WHERE action = 'split_event' AND payload->>'new_event_id' = %s
            ORDER BY id DESC LIMIT 1
            """,
            (str(new_event_id),),
        )
        record = cur.fetchone()
        if record is None:
            raise MergeError(f"Bölme kaydı bulunamadı (events/{new_event_id}).")

        source_event_id = int(record["payload"]["source_event_id"])
        moved = tuple(record["payload"]["moved_article_ids"])

        cur.execute(
            "UPDATE articles SET event_id = %s WHERE id = ANY(%s) AND event_id = %s",
            (source_event_id, list(moved), new_event_id),
        )
        _refresh_event(cur, source_event_id)
        _refresh_event(cur, new_event_id)
        # Boşalan olay silinmez, birleştirilmiş olarak işaretlenir —
        # geçmiş korunur (Spec §7.4 `merged_into_id` gerekçesi).
        cur.execute(
            "UPDATE events SET merged_into_id = %s WHERE id = %s",
            (source_event_id, new_event_id),
        )

        result = SplitResult(source_event_id, new_event_id, moved)
        audit.write(
            "undo_split",
            f"events/{new_event_id}",
            actor="user:admin",
            payload=result.as_dict(),
            cursor=cur,
        )
        conn.commit()

    log.info("split_undone", **result.as_dict())
    return result


# ------------------------------------------------------- denetim kuyruğu
def review_queue(limit: int = 50) -> list[dict[str, Any]]:
    """`needs_review` işaretli olaylar (F2-04)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.id, e.title, e.article_count, e.last_update_at, e.review_flag,
                   (SELECT payload FROM audit_log
                     WHERE action = 'flag_needs_review'
                       AND target = 'events/' || e.id
                     ORDER BY id DESC LIMIT 1) AS flag_payload
            FROM events e
            WHERE e.review_flag = 'needs_review' AND e.merged_into_id IS NULL
            ORDER BY e.last_update_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return list(cur.fetchall())


def resolve_review(event_id: int, decision: str) -> dict[str, Any]:
    """Denetim kararını kaydeder: `verified` veya `rejected`."""
    if decision not in ("verified", "rejected"):
        raise MergeError("Karar 'verified' veya 'rejected' olmalı.")

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE events SET review_flag = %s WHERE id = %s RETURNING id, review_flag",
            (decision, event_id),
        )
        row = cur.fetchone()
        if row is None:
            raise MergeError(f"Olay bulunamadı: {event_id}")
        audit.write(
            "resolve_review",
            f"events/{event_id}",
            actor="user:admin",
            payload={"decision": decision},
            cursor=cur,
        )
        conn.commit()

    log.info("review_resolved", event_id=event_id, decision=decision)
    return dict(row)
