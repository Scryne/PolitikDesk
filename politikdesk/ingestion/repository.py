"""Makale ve kaynak veritabanı erişimi.

Boru hattı ile SQL arasındaki tek katman. Adaptörler ve normalizer
buraya bağımlı değildir (test edilebilirlik).
"""

from __future__ import annotations

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


def list_sources(*, only_active: bool = True) -> list[SourceRow]:
    sql = """
        SELECT id, slug, name, tier, kind, independence_group, access_method,
               tos_status, adapter, base_url, feed_url, extra_feeds,
               keyword_filter, topics, is_active, is_wire_reference
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
                   keyword_filter, topics, is_active, is_wire_reference
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

    def remember(self, article_id: int, content_hash: str, simhash: int,
                 text: str) -> None:
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
                topics, is_manual_import
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (canonical_url) DO NOTHING
            RETURNING id
            """,
            (
                source_id, article.canonical_url, article.title, article.excerpt,
                article.lead_paragraph, article.published_at, article.content_hash,
                _to_signed_bigint(article.simhash), article.lang, article.raw_purge_at,
                near_duplicate_of_id, simhash_distance, independence_key,
                list(article.topics), is_manual_import,
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
) -> None:
    """Çekim turunu günlüğe yazar ve kaynağın sağlık alanlarını günceller."""
    now = datetime.now(UTC)
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO source_fetch_log (
                source_id, duration_ms, items_fetched, items_stored,
                exact_dupes, near_dupes, filtered_out, succeeded, error
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (source_id, duration_ms, items_fetched, items_stored, exact_dupes,
             near_dupes, filtered_out, error is None, error),
        )

        if error is None and items_fetched > 0:
            # ÖNEMLİ: yalnızca gerçekten öğe geldiğinde "başarı" sayılır.
            # HTTP 200 dönen ama boş liste veren bir kaynak sağlıklı değildir —
            # aksi halde JS ile yüklenen bir sayfa sonsuza dek yeşil görünür.
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
        elif last is None or hours_since is not None and hours_since > stale_after_hours:
            status = "red"
        elif row["consecutive_errors"] > 0:
            status = "amber"
        else:
            status = "green"

        report.append({
            **row,
            "hours_since_success": round(hours_since, 1) if hours_since else None,
            "status": status,
        })
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

        if purged:
            cur.execute(
                """
                INSERT INTO audit_log (actor, action, target, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (
                    "system:purge_job",
                    "purge_lead_paragraph",
                    "articles",
                    f'{{"count": {len(purged)}}}',
                ),
            )
        conn.commit()

    if purged:
        log.info("purge_completed", count=len(purged))
    return len(purged)
