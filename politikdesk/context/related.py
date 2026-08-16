"""Tarihsel bağlam: geçmiş benzer olay araması (F2-17).

DoD: Bir enflasyon olayı, önceki ayın enflasyon olayına `same_thread` ile
bağlanıyor.

Bu, Core Loop'un CONTEXTUALIZE adımıdır (Spec §6): "bu konu daha önce ne
zaman gündeme geldi?"

## Kümelemeden farkı

Kümeleme **aynı olayı** arar ve 96 saatlik pencerede çalışır. Bu modül
**farklı ama ilişkili** olayları arar ve pencereyi bilinçli olarak geniş
tutar (varsayılan 400 gün — bir yıllık veri serisi + revizyonlar).

Bu yüzden eşik de farklıdır: kümelemenin T_HIGH'ı (0,86) burada çok
düşüktür — iki ardışık PPK kararı 0,99 benzerlikte ve bunlar **ilişkili
ama ayrı** olaylardır. Tam da bu modülün aradığı şey.

> D16 tanı koşumunun bulgusu burada tersine döner: kümelemede sorun olan
> "şablonlu resmî duyuruların birbirine çok benzemesi", tarihsel bağlamda
> **sinyaldir** — aynı serinin ardışık yayınlarıdır.

## İlişki tipleri (Spec §7.3 `event_relations.relation`)

| Tip | Anlamı |
|---|---|
| `same_thread` | Aynı konu dizisi (aylık enflasyon serisi gibi) |
| `precedes` | Zamansal öncelik |
| `updates` | Aynı verinin revizyonu |
| `contradicts` | Çelişen bilgi |

MVP'de otomatik kurulan tek ilişki `same_thread`'dir; diğerleri elle veya
sonraki fazlarda gelir. Sebep: `updates` ve `contradicts` **yargı**
içerir, `same_thread` yalnızca benzerlik gözlemidir (P4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from politikdesk.db import connection
from politikdesk.nlp.search import DEFAULT_EF_SEARCH, set_ef_search
from politikdesk.observability import get_logger

log = get_logger(__name__)

# Tarihsel bağlam penceresi: bir yıllık seri + revizyonlar için pay.
LOOKBACK_DAYS = 400


# Kümeleme eşiğinden AYRI ve daha yüksektir: burada aranan "aynı olay"
# değil "aynı dizinin başka halkası"dır ve yanlış bağlantı, olay
# sayfasında alakasız bir "geçmiş" göstermek demektir.
#
# ⚠ Sabit 0,80 idi ve BU BİR HATAYDI (B-53 canlı koşumunda yakalandı).
# Değer, Spec §11.4'ün eski T_HIGH tahminine (0,86) göre "yüksek" yazılmıştı;
# F2-14 eşikleri 0,92/0,88'e kalibre ettiğinde bu sabit güncellenmedi ve
# sessizce kümeleme eşiğinin ALTINA düştü. Hashing embedder'la görünmedi
# (benzerlikler zaten düşüktü); e5'e geçince 9 olay 22 bağ üretti:
#
#     "Ulaştırma yatırım projeleri" ↔ "AR-GE harcaması"   0,884
#     "VDK risk analiz sistemi"     ↔ "AR-GE harcaması"   0,834
#
# Doğru türetim: `same_thread` adayı, **kümelenecek kadar benzeyen ama
# zaman penceresi yüzünden kümelenemeyen** olaydır. O halde eşik kümeleme
# T_HIGH'ı olmalıdır — "aynı olay sayılacak kadar benziyor, ama 400 gün
# önce olmuş: demek ki aynı dizinin başka halkası."
#
# Bu türetim veriyle de uyumlu: gerçek bağ (Enflasyon Raporu 2026-III →
# 2026-II) 0,953; farklı TCMB serileri (PPK Özeti ↔ Enflasyon Raporu)
# 0,906 ile eleniyor.
def same_thread_min_similarity() -> float:
    """`same_thread` eşiği — kümeleme T_HIGH'ından türetilir (asla altına düşmez)."""
    from politikdesk.config import get_settings

    return get_settings().cluster_t_high


# Bir olaya bağlanacak azami geçmiş olay. Olay sayfasında 5'ten fazla
# tarihsel bağlam okunabilirliği düşürür.
MAX_RELATIONS = 5


@dataclass(frozen=True)
class RelatedEvent:
    event_id: int
    title: str
    similarity: float
    first_reported_at: Any
    shared_key_entities: tuple[str, ...]


def _parse_vector(literal: str | None) -> list[float]:
    if not literal:
        return []
    return [float(x) for x in literal.strip("[]").split(",") if x]


def find_related(
    event_id: int,
    *,
    min_similarity: float | None = None,
    lookback_days: int = LOOKBACK_DAYS,
    limit: int = MAX_RELATIONS,
) -> list[RelatedEvent]:
    """Bir olaya benzeyen GEÇMİŞ olayları bulur.

    Yalnızca **daha eski** olaylar döner: tarihsel bağlam geriye bakar.
    İleriye bakan bağ, aynı ilişkinin diğer ucundan kurulur.

    `min_similarity` verilmezse ayarlardan türetilir; sabit varsayılan
    kullanılmaz ki eşik kalibrasyonu (F2-14) burayı da kapsasın.
    """
    if min_similarity is None:
        min_similarity = same_thread_min_similarity()
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT centroid_embedding::text AS c, first_reported_at, vertical
            FROM events WHERE id = %s
            """,
            (event_id,),
        )
        source = cur.fetchone()
        if source is None or not source["c"]:
            return []

        set_ef_search(cur, DEFAULT_EF_SEARCH)
        cur.execute(
            """
            SELECT e.id, e.title, e.first_reported_at,
                   1 - (e.centroid_embedding <=> %s::vector) AS similarity
            FROM events e
            WHERE e.id <> %s
              AND e.merged_into_id IS NULL
              AND e.vertical = %s
              AND e.centroid_embedding IS NOT NULL
              AND e.first_reported_at < %s
              AND e.first_reported_at > %s - make_interval(days => %s)
            ORDER BY e.centroid_embedding <=> %s::vector
            LIMIT %s
            """,
            (
                source["c"],
                event_id,
                source["vertical"],
                source["first_reported_at"],
                source["first_reported_at"],
                lookback_days,
                source["c"],
                limit * 3,
            ),
        )
        candidates = [dict(r) for r in cur.fetchall()]

        out: list[RelatedEvent] = []
        for row in candidates:
            if float(row["similarity"]) < min_similarity:
                continue
            cur.execute(
                """
                SELECT en.canonical_name
                FROM event_entities a
                JOIN event_entities b ON b.entity_id = a.entity_id
                JOIN entities en ON en.id = a.entity_id
                WHERE a.event_id = %s AND b.event_id = %s AND en.is_key_entity
                """,
                (event_id, row["id"]),
            )
            shared = tuple(sorted(r["canonical_name"] for r in cur.fetchall()))
            out.append(
                RelatedEvent(
                    event_id=row["id"],
                    title=row["title"],
                    similarity=float(row["similarity"]),
                    first_reported_at=row["first_reported_at"],
                    shared_key_entities=shared,
                )
            )
            if len(out) >= limit:
                break

    return out


def link_related(event_id: int, **kwargs: Any) -> int:
    """Bulunan geçmiş olayları `event_relations`'a `same_thread` olarak yazar.

    İlişki **çift yönlü kaydedilmez**: `from` yeni olay, `to` geçmiş olaydır.
    Sorgu tarafı iki yönü de okuyabilir; çift kayıt, geri alma ve
    tekilleştirmeyi zorlaştırırdı.
    """
    from politikdesk import audit

    related = find_related(event_id, **kwargs)

    with connection() as conn, conn.cursor() as cur:
        if related:
            for item in related:
                cur.execute(
                    """
                    INSERT INTO event_relations
                        (from_event_id, to_event_id, relation, similarity, created_by)
                    VALUES (%s, %s, 'same_thread', %s, 'system')
                    ON CONFLICT (from_event_id, to_event_id, relation) DO UPDATE
                      SET similarity = EXCLUDED.similarity
                    """,
                    (event_id, item.event_id, item.similarity),
                )
            audit.write(
                "link_same_thread",
                f"events/{event_id}",
                actor="system:context@1.0.0",
                payload={
                    "linked": [r.event_id for r in related],
                    "similarities": [round(r.similarity, 4) for r in related],
                },
                cursor=cur,
            )

        # Değerlendirme damgası: sıfır geçmiş bağ bulunsa dahi olay audit loga
        # yazılır; böylece her 30 dakikada bir sonsuz yeniden sorgulanmaz.
        audit.write(
            "context_evaluated",
            f"events/{event_id}",
            actor="system:context@1.0.0",
            payload={"linked_count": len(related)},
            cursor=cur,
        )
        conn.commit()

    log.info("related_events_linked", event_id=event_id, count=len(related))
    return len(related)


def run(limit: int = 50, **kwargs: Any) -> dict[str, int]:
    """Bağlantısı kurulmamış olaylar için tarihsel bağlam turu."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.id FROM events e
            WHERE e.merged_into_id IS NULL
              AND e.centroid_embedding IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM event_relations r WHERE r.from_event_id = e.id
              )
              AND NOT EXISTS (
                SELECT 1 FROM audit_log a
                WHERE a.target = 'events/' || e.id
                  AND a.action = 'context_evaluated'
                  AND a.created_at >= e.last_update_at
              )
            ORDER BY e.last_update_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        event_ids = [r["id"] for r in cur.fetchall()]

    linked = sum(link_related(event_id, **kwargs) for event_id in event_ids)
    stats = {"events_processed": len(event_ids), "relations_created": linked}
    log.info("context_run_complete", **stats)
    return stats
