"""Kümeleme katmanının veritabanı erişimi (F2-01, F2-02).

Karar mantığı `assigner.py`'de saf tutulur; bu modül yalnızca okuma/yazma
yapar. Ayrımın sebebi modül açıklamasında: eşik kalibrasyonu (F2-14) ve
eval koşucusu (F2-16) DB olmadan koşabilmelidir.
"""

from __future__ import annotations

import json
from typing import Any

from politikdesk.clustering.assigner import ArticleFeatures, Assignment, EventCandidate
from politikdesk.clustering.centroid import add_member
from politikdesk.db import connection, fetch_one
from politikdesk.nlp.embedder import to_pgvector
from politikdesk.nlp.search import DEFAULT_EF_SEARCH, set_ef_search
from politikdesk.observability import get_logger

log = get_logger(__name__)

CLUSTERING_ENGINE_VERSION = "clustering@1.0.0"


def pending_clustering(limit: int = 50) -> list[dict[str, Any]]:
    """Kümelenmeyi bekleyen makaleler.

    Ön koşul: embedding VE varlık çıkarımı tamamlanmış olmalı. Varlıkları
    olmayan bir makale, Spec §11.4'ün varlık kısıtını uygulayamaz — kısıtsız
    kümeleme yanlış birleştirme üretir (G2 koşul 3).
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.id, a.title, a.excerpt, a.published_at, a.first_seen_at,
                   a.embedding::text AS embedding,
                   COALESCE(a.vertical, s.vertical, 'macro_economy') AS vertical
            FROM articles a
            LEFT JOIN sources s ON s.id = a.source_id
            WHERE a.event_id IS NULL
              AND a.embedding IS NOT NULL
              AND a.entities_extracted_at IS NOT NULL
            ORDER BY COALESCE(a.published_at, a.first_seen_at)
            LIMIT %s
            """,
            (limit,),
        )
        return list(cur.fetchall())


def _parse_vector(literal: str | None) -> list[float]:
    """pgvector'ün '[0.1,0.2,...]' metin biçimini listeye çevirir."""
    if not literal:
        return []
    return [float(x) for x in literal.strip("[]").split(",") if x]


def _entity_sets(
    cur: Any, table: str, id_column: str, owner_id: int
) -> tuple[frozenset[str], frozenset[str]]:
    cur.execute(
        f"""
        SELECT e.canonical_name, e.is_key_entity
        FROM {table} x
        JOIN entities e ON e.id = x.entity_id
        WHERE x.{id_column} = %s
        """,  # noqa: S608 — table/id_column çağrı yerinde sabit
        (owner_id,),
    )
    rows = cur.fetchall()
    return (
        frozenset(r["canonical_name"] for r in rows),
        frozenset(r["canonical_name"] for r in rows if r["is_key_entity"]),
    )


def load_features(row: dict[str, Any]) -> ArticleFeatures:
    """Bir makale satırını kümeleme özelliklerine çevirir."""
    with connection() as conn, conn.cursor() as cur:
        entities, key_entities = _entity_sets(cur, "article_entities", "article_id", row["id"])
    return ArticleFeatures(
        article_id=row["id"],
        embedding=_parse_vector(row["embedding"]),
        entities=entities,
        key_entities=key_entities,
        published_at=row["published_at"] or row["first_seen_at"],
        text=" ".join(filter(None, (row["title"], row.get("excerpt")))),
        vertical=row.get("vertical", "macro_economy"),
    )


def candidate_events(
    article: ArticleFeatures,
    *,
    limit: int = 20,
    within_hours: int = 96,
    ef_search: int = DEFAULT_EF_SEARCH,
) -> list[EventCandidate]:
    """Spec §11.4 adım 1: son 96 saat, aynı dikey, en yakın 20 olay."""
    literal = to_pgvector(article.embedding)
    with connection() as conn, conn.cursor() as cur:
        set_ef_search(cur, ef_search)
        cur.execute(
            """
            SELECT id, title, summary, last_update_at,
                   1 - (centroid_embedding <=> %s::vector) AS similarity
            FROM events
            WHERE vertical = %s
              AND merged_into_id IS NULL
              AND centroid_embedding IS NOT NULL
              AND last_update_at > now() - make_interval(hours => %s)
            ORDER BY centroid_embedding <=> %s::vector
            LIMIT %s
            """,
            (literal, article.vertical, within_hours, literal, limit),
        )
        rows = list(cur.fetchall())
        if not rows:
            return []

        event_ids = [r["id"] for r in rows]
        cur.execute(
            """
            SELECT x.event_id, e.canonical_name, e.is_key_entity
            FROM event_entities x
            JOIN entities e ON e.id = x.entity_id
            WHERE x.event_id = ANY(%s)
            """,
            (event_ids,),
        )
        ent_map: dict[int, set[str]] = {eid: set() for eid in event_ids}
        key_ent_map: dict[int, set[str]] = {eid: set() for eid in event_ids}
        for erow in cur.fetchall():
            eid = erow["event_id"]
            cname = erow["canonical_name"]
            ent_map[eid].add(cname)
            if erow["is_key_entity"]:
                key_ent_map[eid].add(cname)

        candidates: list[EventCandidate] = []
        for r in rows:
            eid = r["id"]
            candidates.append(
                EventCandidate(
                    event_id=eid,
                    similarity=float(r["similarity"]),
                    entities=frozenset(ent_map[eid]),
                    key_entities=frozenset(key_ent_map[eid]),
                    last_update_at=r["last_update_at"],
                    text_sample=" ".join(filter(None, (r["title"], r["summary"]))),
                )
            )
    return candidates


def create_event(article: ArticleFeatures, row: dict[str, Any]) -> int | None:
    """Yeni olay yaratır; merkez ilk üyenin vektörüdür.

    `title`/`summary` tohum makaleden gelir. Spec §7.3 bu alanlar için
    "LLM üretir, insan düzeltebilir" diyor; LLM başlığı F2-06 sonrası
    yazılır. Boş bırakmak yerine tohum başlığı kullanılır — aksi halde
    denetim kuyruğu (F2-04) okunamaz hale gelir.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO events (title, summary, vertical, centroid_embedding,
                                first_reported_at, last_update_at, article_count)
            VALUES (%s, %s, %s, %s::vector, %s, %s, 1)
            RETURNING id
            """,
            (
                row["title"],
                row.get("excerpt"),
                article.vertical,
                to_pgvector(article.embedding),
                article.published_at,
                article.published_at,
            ),
        )
        event_id = int(fetch_one(cur)["id"])
        attached = _attach_article(
            cur,
            event_id,
            article.article_id,
            similarity=None,
            must_be_unassigned=True,
        )
        if not attached:
            # Yarış durumu: makale başka bir worker tarafından çoktan bir olaya atandı.
            # Oluşturulan olayı geri al ve işlemi iptal et (orphan/ghost event kalmasını önle).
            conn.rollback()
            log.warning("event_creation_aborted_already_assigned", article_id=article.article_id)
            return None

        conn.commit()

    log.info("event_created", event_id=event_id, article_id=article.article_id)
    return event_id


def _attach_article(
    cur: Any,
    event_id: int,
    article_id: int,
    similarity: float | None,
    *,
    must_be_unassigned: bool = False,
) -> bool:
    if must_be_unassigned:
        cur.execute(
            """
            UPDATE articles SET event_id = %s, cluster_score = %s
            WHERE id = %s AND event_id IS NULL
            """,
            (event_id, similarity, article_id),
        )
    else:
        cur.execute(
            "UPDATE articles SET event_id = %s, cluster_score = %s WHERE id = %s",
            (event_id, similarity, article_id),
        )

    if cur.rowcount == 0:
        return False

    # Makalenin varlıkları olayın varlık kümesine katılır — sonraki
    # makalelerin varlık kısıtı bu birikmiş küme üzerinden çalışır.
    cur.execute(
        """
        INSERT INTO event_entities (event_id, entity_id, role)
        SELECT %s, ae.entity_id, 'mentioned'
        FROM article_entities ae
        WHERE ae.article_id = %s
        ON CONFLICT DO NOTHING
        """,
        (event_id, article_id),
    )
    return True


def assign_article(article: ArticleFeatures, decision: Assignment) -> bool:
    """Makaleyi mevcut bir olaya atar ve merkezi artımlı günceller (F2-02)."""
    if decision.event_id is None:
        raise ValueError("assign_article yalnızca mevcut bir olay için çağrılır")

    with connection() as conn, conn.cursor() as cur:
        # Merkez güncellemesi yarış koşumuna açıktır: iki worker aynı olaya
        # aynı anda makale eklerse biri diğerinin sayımını ezer. Satır kilidi
        # bunu engeller; merkez ortalama olduğu için sıra önemsizdir ama
        # `article_count` tutarlı kalmalıdır (F2-02 geri alınabilirlik).
        cur.execute(
            """
            SELECT centroid_embedding::text AS centroid, article_count
            FROM events WHERE id = %s FOR UPDATE
            """,
            (decision.event_id,),
        )
        event = cur.fetchone()
        if event is None:
            raise ValueError(f"Olay bulunamadı: {decision.event_id}")

        attached = _attach_article(
            cur, decision.event_id, article.article_id, decision.similarity, must_be_unassigned=True
        )
        if not attached:
            conn.rollback()
            log.warning(
                "article_assignment_aborted_already_assigned",
                article_id=article.article_id,
                event_id=decision.event_id,
            )
            return False

        new_centroid = add_member(
            _parse_vector(event["centroid"]), event["article_count"], article.embedding
        )

        cur.execute(
            """
            UPDATE events
            SET centroid_embedding = %s::vector,
                article_count      = article_count + 1,
                last_update_at     = GREATEST(last_update_at, %s),
                review_flag        = CASE WHEN %s THEN 'needs_review' ELSE review_flag END
            WHERE id = %s
            """,
            (
                to_pgvector(new_centroid),
                article.published_at,
                decision.needs_review,
                decision.event_id,
            ),
        )

        if decision.needs_review:
            cur.execute(
                """
                INSERT INTO audit_log (actor, action, target, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (
                    f"system:{CLUSTERING_ENGINE_VERSION}",
                    "flag_needs_review",
                    f"events/{decision.event_id}",
                    json.dumps(
                        {
                            "article_id": article.article_id,
                            "similarity": decision.similarity,
                            "reason": decision.review_reason,
                            "numeric_conflicts": [c.describe() for c in decision.numeric_conflicts],
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
        conn.commit()

    log.info(
        "article_assigned",
        event_id=decision.event_id,
        article_id=article.article_id,
        similarity=decision.similarity,
        needs_review=decision.needs_review,
    )
    return True
