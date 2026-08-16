"""Sınırlandırılmış Aday Arama ve Ön Filtreleme Motoru (S3 · Spec v3.4 §14.1).

Bu modül, bir olayın ilişki motoruna (relation_engine) gönderilmeden önce
ilişkili olabilecek en yüksek potansiyelli aday olayları (en fazla 20 aday, sert tavan 50)
süzmesini sağlar. $O(N^2)$ tam tarama patlamasını kesin olarak engeller.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from politikdesk.db import connection
from politikdesk.nlp.entities import jaccard
from politikdesk.observability import get_logger
from politikdesk.political_memory.relation_engine import EventData

log = get_logger(__name__)

DEFAULT_CANDIDATE_LIMIT = 20
ABSOLUTE_MAX_CANDIDATES = 50
MAX_LOOKBACK_DAYS = 400


@dataclass(frozen=True)
class CandidateMatch:
    event_id: int
    title: str
    published_at: datetime
    score: float
    reason: str
    actor: str | None = None
    institution: str | None = None
    topics: tuple[str, ...] = ()
    claims: tuple[dict[str, Any], ...] = ()


def filter_candidates_in_memory(
    source: EventData,
    all_events: list[EventData],
    *,
    limit: int = DEFAULT_CANDIDATE_LIMIT,
) -> list[EventData]:
    r"""Bellek içi aday ön filtreleme — $O(N)$ tarama ile en iyi $\le 20$ adayı seçer."""
    bounded_limit = min(max(1, limit), ABSOLUTE_MAX_CANDIDATES)
    candidates: list[tuple[float, EventData]] = []

    s_entities = source.entities | source.key_entities
    s_topics = set(source.topics)
    s_inst = source.institution.casefold() if source.institution else ""
    s_actor = source.actor.casefold() if source.actor else ""

    for cand in all_events:
        # Kendisiyle ilişki kurulamaz
        if cand.event_id == source.event_id:
            continue

        score = 0.0
        reasons: list[str] = []

        # 1. Aktör Örtüşmesi
        c_actor = cand.actor.casefold() if cand.actor else ""
        if s_actor and c_actor and (s_actor in c_actor or c_actor in s_actor):
            score += 0.40
            reasons.append("actor_match")

        # 2. Kurum Örtüşmesi & Anayasal Bağ
        c_inst = cand.institution.casefold() if cand.institution else ""
        if s_inst and c_inst:
            if s_inst == c_inst or s_inst in c_inst or c_inst in s_inst:
                score += 0.35
                reasons.append("institution_match")
            elif c_inst in ("tbmm", "sayıştay", "cumhurbaşkanlığı") or s_inst in (
                "tbmm",
                "sayıştay",
                "cumhurbaşkanlığı",
            ):
                score += 0.25
                reasons.append("constitutional_link")

        # 3. Konu Örtüşmesi
        c_topics = set(cand.topics)
        shared_t = s_topics & c_topics
        if shared_t:
            score += 0.20 * (len(shared_t) / max(len(s_topics | c_topics), 1))
            reasons.append("topic_overlap")

        # 4. Varlık Jaccard
        c_entities = cand.entities | cand.key_entities
        if s_entities and c_entities:
            j_score = jaccard(s_entities, c_entities)
            if j_score > 0.15:
                score += 0.25 * j_score
                reasons.append(f"entity_jaccard_{j_score:.2f}")

        # 5. Zaman Penceresi Uyumu (400 gün sınır)
        time_diff = abs((cand.published_at - source.published_at).total_seconds())
        if time_diff <= MAX_LOOKBACK_DAYS * 86400:
            score += 0.10

        if score >= 0.25:
            candidates.append((score, cand))

    # Skora göre sırala ve bounded limit ile sınırla
    candidates.sort(key=lambda x: x[0], reverse=True)
    selected = [c[1] for c in candidates[:bounded_limit]]
    return selected


TURKISH_STOPWORDS: frozenset[str] = frozenset(
    {
        "için",
        "olan",
        "dair",
        "daha",
        "gibi",
        "kadar",
        "veya",
        "tarafından",
        "ancak",
        "üzere",
        "bunun",
        "sonra",
        "önce",
        "olarak",
        "oldu",
        "olduğu",
        "olay",
        "ilgili",
        "konuda",
        "birlikte",
        "karşı",
        "göre",
        "eden",
        "edilen",
        "yeni",
        "biri",
        "birkaç",
        "tüm",
        "aynı",
        "farklı",
        "hem",
        "bile",
        "artık",
        "diye",
        "şekilde",
        "ardından",
        "çünkü",
        "böyle",
        "kendi",
        "şöyle",
    }
)


def extract_key_entities_from_text(
    title: str,
    claims: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
) -> frozenset[str]:
    """Başlık ve iddia metinlerinden stopword arındırılmış anahtar kelimeleri çıkarır."""
    key_entities: set[str] = set()
    for c in claims:
        text = c.get("claim_text", "")
        for w in text.split():
            cleaned = w.strip(".,;:\"'()!?[]{}«»-").lower()
            if len(cleaned) >= 4 and cleaned not in TURKISH_STOPWORDS:
                key_entities.add(cleaned)
    for w in title.split():
        cleaned = w.strip(".,;:\"'()!?[]{}«»-").lower()
        if len(cleaned) >= 4 and cleaned not in TURKISH_STOPWORDS:
            key_entities.add(cleaned)
    return frozenset(key_entities)


def fetch_candidate_events_from_db(
    source_event_id: int,
    *,
    limit: int = DEFAULT_CANDIDATE_LIMIT,
) -> list[EventData]:
    """İndeksli sorgularla aday olayları çeker ve EventData'ya dönüştürür."""

    bounded_limit = min(max(1, limit), ABSOLUTE_MAX_CANDIDATES)

    with connection() as conn, conn.cursor() as cur:
        # 1. Kaynak olayı çek
        cur.execute(
            """
            SELECT id, title, first_reported_at, vertical, topic_tags
            FROM events
            WHERE id = %s AND merged_into_id IS NULL;
            """,
            (source_event_id,),
        )
        src_row = cur.fetchone()
        if not src_row:
            return []

        # Kaynak olayın iddialarını çek
        cur.execute(
            """
            SELECT id, claim_text, claim_type, status_reason
            FROM claims
            WHERE event_id = %s;
            """,
            (source_event_id,),
        )
        src_claims = [dict(c) for c in cur.fetchall()]

        # Kaynak olayın varlıklarını çek
        cur.execute(
            """
            SELECT e.canonical_name, e.entity_type
            FROM event_entities ee
            JOIN entities e ON e.id = ee.entity_id
            WHERE ee.event_id = %s;
            """,
            (source_event_id,),
        )
        src_entities = cur.fetchall()

        src_actor: str | None = None
        src_inst: str | None = None
        for ent in src_entities:
            if ent["entity_type"] == "person" and not src_actor:
                src_actor = ent["canonical_name"]
            elif ent["entity_type"] == "institution" and not src_inst:
                src_inst = ent["canonical_name"]

        if not src_actor:
            for c in src_claims:
                reason = c.get("status_reason")
                if isinstance(reason, dict) and reason.get("speaker"):
                    src_actor = reason["speaker"]
                    break

        if not src_inst:
            for c in src_claims:
                reason = c.get("status_reason")
                if isinstance(reason, dict):
                    if reason.get("institution"):
                        src_inst = reason["institution"]
                        break
                    elif reason.get("speaker") and any(
                        k in reason["speaker"]
                        for k in ("Cumhurbaşkanlığı", "TBMM", "Sayıştay", "Bakanlık")
                    ):
                        src_inst = reason["speaker"]
                        break

        src_topics = tuple(src_row["topic_tags"]) if src_row.get("topic_tags") else ()
        src_entities_set = frozenset(ent["canonical_name"] for ent in src_entities)
        src_key_entities = extract_key_entities_from_text(src_row["title"], src_claims)

        source_data = EventData(
            event_id=src_row["id"],
            title=src_row["title"],
            published_at=src_row["first_reported_at"],
            actor=src_actor,
            institution=src_inst,
            entities=src_entities_set,
            key_entities=src_key_entities,
            topics=src_topics,
            claims=tuple(src_claims),
            vertical=src_row["vertical"],
        )

        # 2. Aday olayları çek (Aynı dikey veya promise taşıyanlar, 400 gün sınır)
        cur.execute(
            """
            SELECT e.id, e.title, e.first_reported_at, e.vertical, e.topic_tags
            FROM events e
            WHERE e.id <> %s
              AND e.merged_into_id IS NULL
              AND e.first_reported_at >= (%s::timestamptz - INTERVAL '400 days')
              AND (
                  e.vertical = %s
                  OR EXISTS (
                      SELECT 1 FROM claims c
                      WHERE c.event_id = e.id AND c.claim_type = 'promise'
                  )
              )
            ORDER BY e.first_reported_at DESC
            LIMIT %s;
            """,
            (source_event_id, src_row["first_reported_at"], src_row["vertical"], bounded_limit * 2),
        )
        candidate_rows = cur.fetchall()
        if not candidate_rows:
            return []

        cand_ids = [r["id"] for r in candidate_rows]

        # 3. BATCH: Tüm adayların iddialarını tek sorguda çek (N+1 yok)
        cur.execute(
            """
            SELECT event_id, id, claim_text, claim_type, status_reason
            FROM claims
            WHERE event_id = ANY(%s);
            """,
            (cand_ids,),
        )
        cand_claims_map: dict[int, list[dict[str, Any]]] = {cid: [] for cid in cand_ids}
        for c in cur.fetchall():
            eid = c["event_id"]
            if eid in cand_claims_map:
                cand_claims_map[eid].append(dict(c))

        # 4. BATCH: Tüm adayların varlıklarını tek sorguda çek (N+1 yok)
        cur.execute(
            """
            SELECT ee.event_id, e.canonical_name, e.entity_type
            FROM event_entities ee
            JOIN entities e ON e.id = ee.entity_id
            WHERE ee.event_id = ANY(%s);
            """,
            (cand_ids,),
        )
        cand_entities_map: dict[int, set[str]] = {cid: set() for cid in cand_ids}
        cand_actor_map: dict[int, str | None] = dict.fromkeys(cand_ids)
        cand_inst_map: dict[int, str | None] = dict.fromkeys(cand_ids)

        for ent in cur.fetchall():
            eid = ent["event_id"]
            if eid in cand_entities_map:
                cand_entities_map[eid].add(ent["canonical_name"])
                if ent["entity_type"] == "person" and not cand_actor_map[eid]:
                    cand_actor_map[eid] = ent["canonical_name"]
                elif ent["entity_type"] == "institution" and not cand_inst_map[eid]:
                    cand_inst_map[eid] = ent["canonical_name"]

        # 5. Aday EventData nesnelerini tam hidratize et
        candidates_pool: list[EventData] = []
        for r in candidate_rows:
            cid = r["id"]
            c_claims = cand_claims_map.get(cid, [])
            c_actor = cand_actor_map.get(cid)
            c_inst = cand_inst_map.get(cid)

            # Speaker/institution fallback
            if not c_actor:
                for c in c_claims:
                    reason = c.get("status_reason")
                    if isinstance(reason, dict) and reason.get("speaker"):
                        c_actor = reason["speaker"]
                        break

            if not c_inst:
                for c in c_claims:
                    reason = c.get("status_reason")
                    if isinstance(reason, dict):
                        if reason.get("institution"):
                            c_inst = reason["institution"]
                            break
                        elif reason.get("speaker") and any(
                            k in reason["speaker"]
                            for k in ("Cumhurbaşkanlığı", "TBMM", "Sayıştay", "Bakanlık")
                        ):
                            c_inst = reason["speaker"]
                            break

            c_topics = tuple(r["topic_tags"]) if r.get("topic_tags") else ()
            c_entities_set = frozenset(cand_entities_map.get(cid, set()))
            c_key_entities = extract_key_entities_from_text(r["title"], c_claims)

            candidates_pool.append(
                EventData(
                    event_id=cid,
                    title=r["title"],
                    published_at=r["first_reported_at"],
                    actor=c_actor,
                    institution=c_inst,
                    entities=c_entities_set,
                    key_entities=c_key_entities,
                    topics=c_topics,
                    claims=tuple(c_claims),
                    vertical=r["vertical"],
                )
            )

        selected = filter_candidates_in_memory(
            source_data,
            candidates_pool,
            limit=bounded_limit,
        )
        if selected:
            return selected
        return candidates_pool[:bounded_limit]
