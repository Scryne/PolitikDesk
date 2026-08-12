"""pgvector ANN sorgu katmanı (F1-14).

DoD: 10.000 makalede en yakın 20 komşu < 50 ms.

HNSW indeksi `migrations/0001_initial.sql`'de tanımlıdır. Bu modül
sorgu tarafını ve indeks ayarını sağlar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from politikdesk.db import connection
from politikdesk.nlp.embedder import to_pgvector
from politikdesk.observability import get_logger

log = get_logger(__name__)

# HNSW arama genişliği. Yükseltmek geri çağırmayı (recall) artırır,
# gecikmeyi de artırır. 10k ölçeğinde 64 iyi bir denge.
DEFAULT_EF_SEARCH = 64


@dataclass(frozen=True)
class Neighbor:
    article_id: int
    title: str
    source_slug: str
    similarity: float
    published_at: Any


def set_ef_search(cur: Any, ef_search: int) -> None:
    """HNSW arama genişliğini işlem süresince ayarlar.

    ⚠ `SET LOCAL hnsw.ef_search = %s` ÇALIŞMAZ: Postgres'te `SET` bind
    parametresi kabul etmez, `syntax error at or near "$1"` döner. Bu hata
    Faz 1'de fark edilmedi çünkü kod yolu canlı veritabanına karşı hiç
    koşmamıştı; Faz 2'nin ilk canlı kümeleme turunda ortaya çıktı.

    `set_config(..., is_local => true)` parametrelenebilir ve aynı işi yapar.
    """
    if not isinstance(ef_search, int) or not 1 <= ef_search <= 1000:
        raise ValueError(f"ef_search 1-1000 aralığında bir tam sayı olmalı: {ef_search!r}")
    cur.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(ef_search),))


# Geriye dönük ad — modül içinde kullanılıyor.
_set_ef_search = set_ef_search


def nearest_articles(
    vector: list[float],
    *,
    limit: int = 20,
    within_hours: int | None = 96,
    exclude_article_id: int | None = None,
    ef_search: int = DEFAULT_EF_SEARCH,
) -> list[Neighbor]:
    """Verilen vektöre en yakın makaleleri döndürür.

    `<=>` pgvector'ün kosinüs MESAFESİdir; benzerlik = 1 - mesafe.
    """
    conditions = ["a.embedding IS NOT NULL"]
    params: list[Any] = []

    if within_hours is not None:
        conditions.append("a.first_seen_at > now() - make_interval(hours => %s)")
        params.append(within_hours)
    if exclude_article_id is not None:
        conditions.append("a.id <> %s")
        params.append(exclude_article_id)

    where = " AND ".join(conditions)
    query = f"""
        SELECT a.id, a.title, s.slug AS source_slug, a.published_at,
               1 - (a.embedding <=> %s::vector) AS similarity
        FROM articles a
        JOIN sources s ON s.id = a.source_id
        WHERE {where}
        ORDER BY a.embedding <=> %s::vector
        LIMIT %s
    """  # noqa: S608 — `where` yalnızca sabit parçalardan kuruluyor

    literal = to_pgvector(vector)
    with connection() as conn, conn.cursor() as cur:
        _set_ef_search(cur, ef_search)
        cur.execute(query, [literal, *params, literal, limit])
        rows = cur.fetchall()

    return [
        Neighbor(
            article_id=r["id"],
            title=r["title"],
            source_slug=r["source_slug"],
            similarity=float(r["similarity"]),
            published_at=r["published_at"],
        )
        for r in rows
    ]


def nearest_events(
    vector: list[float],
    *,
    vertical: str = "macro_economy",
    limit: int = 20,
    within_hours: int = 96,
    ef_search: int = DEFAULT_EF_SEARCH,
) -> list[dict[str, Any]]:
    """Aday olayları getirir (Spec §11.4 adım 1 — Faz 2'de kullanılacak)."""
    literal = to_pgvector(vector)
    with connection() as conn, conn.cursor() as cur:
        _set_ef_search(cur, ef_search)
        cur.execute(
            """
            SELECT id, title, first_reported_at, last_update_at,
                   1 - (centroid_embedding <=> %s::vector) AS similarity
            FROM events
            WHERE vertical = %s
              AND merged_into_id IS NULL
              AND centroid_embedding IS NOT NULL
              AND last_update_at > now() - make_interval(hours => %s)
            ORDER BY centroid_embedding <=> %s::vector
            LIMIT %s
            """,
            (literal, vertical, within_hours, literal, limit),
        )
        return list(cur.fetchall())


def benchmark(vector: list[float], *, limit: int = 20, runs: int = 5) -> dict[str, float]:
    """F1-14 DoD ölçümü: komşu sorgusu gecikmesi."""
    import time

    durations: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        nearest_articles(vector, limit=limit, within_hours=None)
        durations.append((time.perf_counter() - started) * 1000)

    durations.sort()
    return {
        "runs": runs,
        "min_ms": round(durations[0], 2),
        "median_ms": round(durations[len(durations) // 2], 2),
        "max_ms": round(durations[-1], 2),
    }
