"""Makale ve kaynak veritabanı erişimi.

Boru hattı ile SQL arasındaki tek katman. Adaptörler ve normalizer
buraya bağımlı değildir (test edilebilirlik).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from politikdesk.db import connection
from politikdesk.ingestion.models import NormalizedArticle
from politikdesk.observability import get_logger

log = get_logger(__name__)

# Tekrar karşılaştırması bu pencereyle sınırlanır: tüm tabloyu taramak
# hem gereksiz hem de yanlış (6 ay arayla aynı başlık farklı olaydır).
DEDUP_WINDOW_HOURS = 96


@dataclass(frozen=True)
class SourceRow:
    id: int
    slug: str
    name: str
    tier: int
    kind: str
    independence_group: str | None
    access_method: str
    tos_status: str
    adapter: str | None
    base_url: str | None
    feed_url: str | None
    extra_feeds: list[str]
    keyword_filter: list[str]
    topics: list[str]
    is_active: bool
    is_wire_reference: bool
    vertical: str = "macro_economy"


def list_sources(*, only_active: bool = True) -> list[SourceRow]:
    sql = """
        SELECT id, slug, name, tier, kind, independence_group, access_method,
               tos_status, adapter, base_url, feed_url, extra_feeds,
               keyword_filter, topics, is_active, is_wire_reference, vertical
        FROM sources
    """
    if only_active:
        sql += " WHERE is_active"
    sql += " ORDER BY tier, slug"

    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return [SourceRow(**row) for row in cur.fetchall()]


def get_source(slug: str) -> SourceRow | None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, slug, name, tier, kind, independence_group, access_method,
                   tos_status, adapter, base_url, feed_url, extra_feeds,
                   keyword_filter, topics, is_active, is_wire_reference, vertical
            FROM sources WHERE slug = %s
            """,
            (slug,),
        )
        row = cur.fetchone()
        return SourceRow(**row) if row else None


@dataclass
class DedupWindow:
    """Tekilleştirme karşılaştırması için son N saatlik parmak izleri.

    Metinler de taşınır çünkü Spec §8.2 iki sinyal tanımlar: simhash
    mesafesi VE ortak n-gram oranı. İkincisi kısa metinlerde belirleyicidir.
    """

    hashes: dict[str, int]
    simhashes: list[tuple[int, int]]
    texts: dict[int, str]

    def remember(self, article_id: int, content_hash: str, simhash: int, text: str) -> None:
        """Aynı tur içinde eklenen makaleler de karşılaştırmaya girsin."""
        self.hashes[content_hash] = article_id
        self.simhashes.append((article_id, simhash))
        self.texts[article_id] = text


def load_dedup_window(hours: int = DEDUP_WINDOW_HOURS) -> DedupWindow:
    """Tekilleştirme için son N saatlik parmak izlerini yükler."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, content_hash, simhash, title, excerpt FROM articles
            WHERE first_seen_at > now() - make_interval(hours => %s)
            """,
            (hours,),
        )
        rows = cur.fetchall()

    return DedupWindow(
        hashes={r["content_hash"]: r["id"] for r in rows},
        simhashes=[(r["id"], _from_signed_bigint(r["simhash"] or 0)) for r in rows],
        texts={r["id"]: f"{r['title']} {r['excerpt'] or ''}" for r in rows},
    )


def _from_signed_bigint(value: int) -> int:
    """Postgres BIGINT'i 64-bit işaretsiz simhash'e geri çevirir."""
    return value + (1 << 64) if value < 0 else value


def url_exists(canonical_url: str) -> bool:
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM articles WHERE canonical_url = %s", (canonical_url,))
        return cur.fetchone() is not None


def insert_article(
    article: NormalizedArticle,
    *,
    source_id: int,
    independence_key: str,
    near_duplicate_of_id: int | None = None,
    simhash_distance: int | None = None,
    is_manual_import: bool = False,
) -> int | None:
    """Makaleyi kaydeder. `canonical_url` çakışırsa None döner (tekrar)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO articles (
                source_id, canonical_url, title, excerpt, lead_paragraph,
                published_at, content_hash, simhash, lang, raw_purge_at,
                near_duplicate_of_id, simhash_distance, independence_key,
                topics, is_manual_import, official_value, vertical
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
            ON CONFLICT (canonical_url) DO NOTHING
            RETURNING id
            """,
            (
                source_id,
                article.canonical_url,
                article.title,
                article.excerpt,
                article.lead_paragraph,
                article.published_at,
                article.content_hash,
                _to_signed_bigint(article.simhash),
                article.lang,
                article.raw_purge_at,
                near_duplicate_of_id,
                simhash_distance,
                independence_key,
                list(article.topics),
                is_manual_import,
                json.dumps(article.official_value, ensure_ascii=False)
                if article.official_value
                else None,
                article.vertical,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return row["id"] if row else None


def _to_signed_bigint(value: int) -> int:
    """64-bit işaretsiz simhash'i Postgres BIGINT aralığına taşır."""
    return value - (1 << 64) if value >= (1 << 63) else value


def record_fetch(
    source_id: int,
    *,
    duration_ms: int,
    items_fetched: int,
    items_stored: int,
    exact_dupes: int,
    near_dupes: int,
    filtered_out: int,
    error: str | None,
    partial_failures: Sequence[str] = (),
    items_parsed: int | None = None,
) -> None:
    """Çekim turunu günlüğe yazar ve kaynağın sağlık alanlarını günceller.

    `succeeded` sütununun anlamı (B-80'de düzeltildi): **tur kullanılabilir
    sonuç üretti mi**. Eskiden "boru hattına istisna sızmadı mı" demekti;
    adaptörler hatayı içeride yuttuğu için Resmî Gazete'nin TLS hatası ham
    kayıtta `succeeded=true, 0 öğe` diye görünüyordu. Sağlık panosu bunu
    telafi ediyordu (0 öğe → kırmızı), yani ürün yanılmıyordu — ama kayıt
    yanılıyordu.

    `partial_failures`: öğe GELDİ ama bazı akışlar düştü. Tur başarılı
    sayılır (kaynağı kırmızıya çekmek yanlış alarm olurdu), yalnızca
    `error` sütununa iz düşülür.

    `items_parsed`: adaptörün konu filtresinden **ÖNCE** ayrıştırdığı ham
    kalem sayısı. `None` = adaptör ayrım yapmıyor; o zaman `items_fetched`
    ham sayının kendisidir ve davranış değişmez (89 kaynağın 88'i böyle).

    Ayrım neden gerekti (19 Ağustos 2026, ölçüm `adapters/base.py`
    `note_parsed` başlığında): "0 öğe → sağlıksız" kuralı, *sayfadan hiç
    kalem çıkmadı* ile *kalemler çıktı ama konu filtresi hiçbirini
    geçirmedi* durumlarını aynı kefeye koyuyordu. İkincisi Resmî Gazete
    için normaldir ve 7 günde 516 kez yaşanmıştı; kaynak kalıcı kırmızıya
    düşmüş, ardışık hata sayacı 758'e çıkmıştı.

    ⛔ İlk durum arıza olmaya DEVAM EDER. B-42/B-43'ün korumaya çalıştığı
    şey buydu: uç 200 döner, gövde beklenen şey değildir, tur sessizce
    başarılı görünür.
    """
    now = datetime.now(UTC)
    logged_error = error
    if logged_error is None and partial_failures:
        logged_error = "KISMİ: " + "; ".join(partial_failures)[:900]

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO source_fetch_log (
                source_id, duration_ms, items_fetched, items_stored,
                exact_dupes, near_dupes, filtered_out, succeeded, error
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                source_id,
                duration_ms,
                items_fetched,
                items_stored,
                exact_dupes,
                near_dupes,
                filtered_out,
                error is None,
                logged_error,
            ),
        )

        # "Kaynağa ulaşıldı ve içerik ÜRETTİ mi?" — konu filtresinin ne
        # kadarını geçirdiği ayrı bir sorudur.
        #
        # ÖNEMLİ: yalnızca gerçekten kalem geldiğinde "başarı" sayılır.
        # HTTP 200 dönen ama boş liste veren bir kaynak sağlıklı değildir —
        # aksi halde JS ile yüklenen bir sayfa sonsuza dek yeşil görünür
        # (B-42/B-43). Bu koruma DURUYOR; değişen tek şey, ölçünün konu
        # filtresinden ÖNCEKİ sayı olması.
        uretken = items_fetched > 0 or (items_parsed or 0) > 0

        if error is None and uretken:
            cur.execute(
                """
                UPDATE sources SET last_fetched_at = %s, last_success_at = %s,
                    consecutive_errors = 0, last_error = NULL
                WHERE id = %s
                """,
                (now, now, source_id),
            )
        elif error is None:
            cur.execute(
                """
                UPDATE sources SET last_fetched_at = %s,
                    last_error = 'Cekim basarili ama 0 oge dondu',
                    last_error_at = %s,
                    consecutive_errors = consecutive_errors + 1
                WHERE id = %s
                """,
                (now, now, source_id),
            )
        else:
            cur.execute(
                """
                UPDATE sources SET last_fetched_at = %s, last_error = %s,
                    last_error_at = %s, consecutive_errors = consecutive_errors + 1
                WHERE id = %s
                """,
                (now, error[:500], now, source_id),
            )
        conn.commit()


def health_report(stale_after_hours: int = 6) -> list[dict[str, Any]]:
    """Kaynak başına akış durumu (F1-19).

    DoD: bir kaynak 6 saattir veri vermiyorsa kırmızı.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.slug, s.name, s.tier, s.is_active, s.tos_status,
                   s.last_success_at, s.last_error, s.last_error_at,
                   s.consecutive_errors,
                   (SELECT count(*) FROM articles a
                     WHERE a.source_id = s.id
                       AND a.first_seen_at > now() - interval '24 hours')
                     AS articles_24h,
                   (SELECT count(*) FROM articles a WHERE a.source_id = s.id)
                     AS articles_total
            FROM sources s
            ORDER BY s.tier, s.slug
            """
        )
        rows = cur.fetchall()

    now = datetime.now(UTC)
    report: list[dict[str, Any]] = []
    for row in rows:
        last = row["last_success_at"]
        hours_since = (now - last).total_seconds() / 3600 if last else None

        if not row["is_active"]:
            status = "inactive"
        elif row["tos_status"] == "pending_review":
            status = "blocked"
        elif last is None or (hours_since is not None and hours_since > stale_after_hours):
            status = "red"
        elif row["consecutive_errors"] > 0:
            status = "amber"
        else:
            status = "green"

        report.append(
            {
                **row,
                "hours_since_success": round(hours_since, 1) if hours_since else None,
                "status": status,
            }
        )
    return report


def purge_expired_bodies(limit: int = 5_000) -> int:
    """`raw_purge_at` geçmiş kayıtlarda `lead_paragraph`'ı NULL yapar (F1-12).

    DoD: purge çalıştı; `audit_log`'a yazılıyor.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            WITH expired AS (
                SELECT id FROM articles
                WHERE lead_paragraph IS NOT NULL
                  AND raw_purge_at IS NOT NULL
                  AND raw_purge_at < now()
                LIMIT %s
            )
            UPDATE articles SET lead_paragraph = NULL
            WHERE id IN (SELECT id FROM expired)
            RETURNING id
            """,
            (limit,),
        )
        purged = [r["id"] for r in cur.fetchall()]

        cur.execute(
            """
            INSERT INTO audit_log (actor, action, target, payload)
            VALUES (%s, %s, %s, %s::jsonb)
            """,
            (
                "system:purge_job",
                "purge_expired_bodies",
                "articles",
                json.dumps({"count": len(purged)}),
            ),
        )
        conn.commit()

    if purged:
        log.info("purge_completed", count=len(purged))
    return len(purged)
