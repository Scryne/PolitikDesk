"""NLP katmanının veritabanı erişimi — embedding ve varlık kaydı."""

from __future__ import annotations

from typing import Any

from politikdesk.db import connection
from politikdesk.nlp.embedder import to_pgvector
from politikdesk.nlp.entities import ExtractedEntity
from politikdesk.observability import get_logger

log = get_logger(__name__)


def pending_embedding(limit: int = 50) -> list[dict[str, Any]]:
    """Henüz embed edilmemiş makaleler (en eski önce)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, excerpt FROM articles
            WHERE embedded_at IS NULL
            ORDER BY first_seen_at
            LIMIT %s
            """,
            (limit,),
        )
        return list(cur.fetchall())


def save_embeddings(vectors: dict[int, list[float]]) -> int:
    """Makale embedding'lerini yazar ve `embedded_at` damgasını basar."""
    if not vectors:
        return 0
    with connection() as conn, conn.cursor() as cur:
        for article_id, vector in vectors.items():
            cur.execute(
                """
                UPDATE articles
                SET embedding = %s::vector, embedded_at = now()
                WHERE id = %s
                """,
                (to_pgvector(vector), article_id),
            )
        conn.commit()
    return len(vectors)


def pending_entities(limit: int = 100) -> list[dict[str, Any]]:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, excerpt FROM articles
            WHERE entities_extracted_at IS NULL
            ORDER BY first_seen_at
            LIMIT %s
            """,
            (limit,),
        )
        return list(cur.fetchall())


def upsert_entity(entity: ExtractedEntity, aliases: tuple[str, ...] = ()) -> int:
    """Varlığı sözlüğe ekler veya alias'larını genişletir (F1-16)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO entities (canonical_name, entity_type, aliases, is_key_entity)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (canonical_name, entity_type) DO UPDATE
              -- COALESCE zorunlu: iki dizi de boşsa array_agg NULL döner ve
              -- NOT NULL kısıtını ihlal eder (kişi varlıklarında tipik durum).
              SET aliases = COALESCE(
                    (SELECT array_agg(DISTINCT a)
                     FROM unnest(entities.aliases || EXCLUDED.aliases) AS a),
                    '{}'
                  ),
                  is_key_entity = entities.is_key_entity OR EXCLUDED.is_key_entity
            RETURNING id
            """,
            (entity.canonical_name, entity.entity_type, list(aliases),
             entity.is_key_entity),
        )
        entity_id = cur.fetchone()["id"]
        conn.commit()
        return entity_id


def link_article_entities(article_id: int, entity_ids: list[int]) -> None:
    if not entity_ids:
        return
    with connection() as conn, conn.cursor() as cur:
        for entity_id in entity_ids:
            cur.execute(
                """
                INSERT INTO article_entities (article_id, entity_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
                """,
                (article_id, entity_id),
            )
        conn.commit()


def mark_entities_extracted(article_ids: list[int]) -> None:
    if not article_ids:
        return
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE articles SET entities_extracted_at = now() WHERE id = ANY(%s)",
            (article_ids,),
        )
        conn.commit()


def article_entities(article_id: int) -> list[dict[str, Any]]:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.id, e.canonical_name, e.entity_type, e.is_key_entity
            FROM article_entities ae
            JOIN entities e ON e.id = ae.entity_id
            WHERE ae.article_id = %s
            ORDER BY e.is_key_entity DESC, e.canonical_name
            """,
            (article_id,),
        )
        return list(cur.fetchall())


def embedding_coverage() -> dict[str, int]:
    """Sağlık paneli için embedding kapsama oranı."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              count(*) AS total,
              count(*) FILTER (WHERE embedding IS NOT NULL) AS embedded,
              count(*) FILTER (WHERE entities_extracted_at IS NOT NULL) AS entities_done
            FROM articles
            """
        )
        return dict(cur.fetchone())
