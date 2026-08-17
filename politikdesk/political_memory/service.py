"""Political Memory v1 — aktör ve iddia zinciri sorgu servisi (B-15 · Spec v3.4 §7.3, §8.3).

Bu servis, bir aktörün (kişi/kurum/parti) geçmiş beyanlarını, vaatlerini
ve bu iddialara bağlı olay ilişkilerini (`event_relations`) sorgular.
"Hesap Sor" açısının kanıt ve bağlam zeminini oluşturur.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from politikdesk.db import connection
from politikdesk.observability import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class MemoryEntry:
    """Geçmiş bir olaya ait aktör iddia/beyan kaydı."""

    event_id: int
    event_title: str
    claim_id: int
    claim_text: str
    claim_type: str
    evidence_status: str
    first_reported_at: str
    quote_span: str = ""
    source_names: tuple[str, ...] = ()
    relation_to_current: str | None = None


@dataclass
class ActorMemory:
    """Bir aktörün geçmiş beyan ve vaat hafızası."""

    actor_name: str
    total_claims: int
    promises: list[MemoryEntry] = field(default_factory=list)
    attributions: list[MemoryEntry] = field(default_factory=list)
    facts_and_numbers: list[MemoryEntry] = field(default_factory=list)
    relation_chains: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_name": self.actor_name,
            "total_claims": self.total_claims,
            "promises": [asdict(p) for p in self.promises],
            "attributions": [asdict(a) for a in self.attributions],
            "facts_and_numbers": [asdict(f) for f in self.facts_and_numbers],
            "relation_chains": self.relation_chains,
        }


def build_actor_memory(
    actor_name: str,
    entries: list[MemoryEntry],
    relations: list[dict[str, Any]] | None = None,
) -> ActorMemory:
    """Ham bellek girdilerinden yapılandırılmış ActorMemory nesnesi kurar."""
    mem = ActorMemory(
        actor_name=actor_name,
        total_claims=len(entries),
        relation_chains=relations or [],
    )
    for e in entries:
        if e.claim_type == "promise":
            mem.promises.append(e)
        elif e.claim_type == "attribution":
            mem.attributions.append(e)
        else:
            mem.facts_and_numbers.append(e)
    return mem


def filter_contradicting_or_fulfilling_memories(
    mem: ActorMemory,
) -> list[MemoryEntry]:
    """Gerçekleşme veya çelişki ilişkisi taşıyan kritik kayıtları süzer."""
    return [
        p
        for p in mem.promises + mem.attributions
        if p.relation_to_current in ("contradicts", "fulfils", "fails", "updates")
    ]


def record_relation(
    from_event_id: int,
    to_event_id: int,
    relation: str,
    similarity: float = 1.0,
    created_by: str = "system",
    confidence: float = 1.0,
    evidence_payload: dict[str, Any] | None = None,
    status: str = "inferred",
) -> None:
    """Olaylar arası ilişki kaydeder (precedes, updates, contradicts, fulfils, fails)."""

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO event_relations (
                from_event_id, to_event_id, relation, similarity, created_by,
                confidence, evidence_payload, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (from_event_id, to_event_id, relation) DO UPDATE
            SET similarity = EXCLUDED.similarity,
                confidence = EXCLUDED.confidence,
                evidence_payload = EXCLUDED.evidence_payload,
                status = EXCLUDED.status

            """,
            (
                from_event_id,
                to_event_id,
                relation,
                similarity,
                created_by,
                confidence,
                json.dumps(evidence_payload or {}),
                status,
            ),
        )
        conn.commit()


def get_actor_memory(actor_name: str) -> ActorMemory:
    """Veritabanından aktöre ait iddiaları ve ilişki zincirini yükler."""
    entries: list[MemoryEntry] = []
    chains: list[dict[str, Any]] = []

    with connection() as conn, conn.cursor() as cur:
        # Aktörle eşleşen iddiaları çek
        pattern = f"%{actor_name}%"
        cur.execute(
            """
            SELECT c.id as claim_id, c.claim_text, c.claim_type, c.evidence_status,
                   c.event_id, e.title as event_title, e.first_reported_at,
                   c.status_reason
            FROM claims c
            JOIN events e ON e.id = c.event_id
            WHERE c.claim_text ILIKE %s
               OR c.status_reason->>'speaker' ILIKE %s
               OR EXISTS (
                   SELECT 1 FROM articles a
                   WHERE a.event_id = e.id AND a.title ILIKE %s
               )
               OR EXISTS (
                   SELECT 1 FROM event_entities ee
                   JOIN entities en ON en.id = ee.entity_id
                   WHERE ee.event_id = e.id AND en.canonical_name ILIKE %s
               )
            ORDER BY e.first_reported_at DESC
            LIMIT 100;
            """,
            (pattern, pattern, pattern, pattern),
        )
        rows = cur.fetchall()
        for r in rows:
            reported = r["first_reported_at"].isoformat() if r["first_reported_at"] else ""
            status_reason = r.get("status_reason") or {}
            quote = status_reason.get("quote_span", "") if isinstance(status_reason, dict) else ""
            entries.append(
                MemoryEntry(
                    event_id=r["event_id"],
                    event_title=r["event_title"],
                    claim_id=r["claim_id"],
                    claim_text=r["claim_text"],
                    claim_type=r["claim_type"],
                    evidence_status=r["evidence_status"],
                    first_reported_at=reported,
                    quote_span=quote,
                )
            )

        # Aktörün olaylarına bağlı ilişkileri çek
        if entries:
            event_ids = list({e.event_id for e in entries})
            cur.execute(
                """
                SELECT r.from_event_id, r.to_event_id, r.relation, r.similarity,
                       r.confidence, r.status, r.evidence_payload,
                       e1.title as from_title, e2.title as to_title
                FROM event_relations r
                JOIN events e1 ON e1.id = r.from_event_id
                JOIN events e2 ON e2.id = r.to_event_id
                WHERE r.from_event_id = ANY(%s) OR r.to_event_id = ANY(%s)
                ORDER BY r.created_at DESC;
                """,
                (event_ids, event_ids),
            )
            for rel in cur.fetchall():
                chains.append(
                    {
                        "from_event_id": rel["from_event_id"],
                        "from_title": rel["from_title"],
                        "to_event_id": rel["to_event_id"],
                        "to_title": rel["to_title"],
                        "relation": rel["relation"],
                        "similarity": rel["similarity"],
                        "confidence": rel.get("confidence", 1.0),
                        "status": rel.get("status", "inferred"),
                        "evidence_payload": rel.get("evidence_payload") or {},
                    }
                )

    return build_actor_memory(actor_name, entries, chains)


def get_promise_tracker(limit: int = 50) -> list[dict[str, Any]]:
    """Tüm vaat (promise) türündeki iddiaları ve gerçekleşme durumlarını listeler."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id as claim_id, c.claim_text, c.evidence_status, c.event_id,
                   e.title as event_title, e.first_reported_at,
                   c.status_reason,
                   rel.relation as outcome_relation,
                   rel.status as relation_status,
                   rel.evidence_payload
            FROM claims c
            JOIN events e ON e.id = c.event_id
            LEFT JOIN LATERAL (
                SELECT r.relation, r.status, r.evidence_payload
                FROM event_relations r
                WHERE r.from_event_id = e.id
                  AND r.relation IN ('fulfils', 'fails', 'contradicts')
                ORDER BY r.created_at DESC
                LIMIT 1
            ) rel ON TRUE
            WHERE c.claim_type = 'promise'
            ORDER BY e.first_reported_at DESC
            LIMIT %s;
            """,
            (limit,),
        )
        out = []
        for r in cur.fetchall():
            reported = r["first_reported_at"].isoformat() if r["first_reported_at"] else ""
            status_reason = r.get("status_reason") or {}
            out.append(
                {
                    "claim_id": r["claim_id"],
                    "claim_text": r["claim_text"],
                    "evidence_status": r["evidence_status"],
                    "event_id": r["event_id"],
                    "event_title": r["event_title"],
                    "first_reported_at": reported,
                    "speaker": status_reason.get("speaker", "Bilinmeyen Aktör")
                    if isinstance(status_reason, dict)
                    else "Bilinmeyen Aktör",
                    "outcome_relation": r["outcome_relation"] or "pending",
                    "relation_status": r.get("relation_status") or "unresolved",
                    "evidence_payload": r.get("evidence_payload") or {},
                }
            )
        return out


def get_accountability_digest(limit: int = 50) -> list[dict[str, Any]]:
    """'Hesap Sor' hesap verebilirlik özeti: vaat vs eylem/oylama/denetim karşılaştırması."""
    promises = get_promise_tracker(limit=limit)

    digest = []
    for p in promises:
        digest.append(
            {
                "claim_id": p["claim_id"],
                "event_title": p["event_title"],
                "promise_text": p["claim_text"],
                "speaker": p["speaker"],
                "reported_at": p["first_reported_at"],
                "status": p["outcome_relation"],
                "relation_status": p["relation_status"],
                "evidence_status": p["evidence_status"],
                "evidence_payload": p["evidence_payload"],
            }
        )
    return digest


def list_tracked_actors(limit: int = 50) -> list[dict[str, Any]]:
    """Kayıtlı aktörleri ve varlıkları listeler."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT canonical_name as name, entity_type, is_key_entity
            FROM entities
            WHERE entity_type IN ('person', 'institution')
            ORDER BY is_key_entity DESC, canonical_name ASC
            LIMIT %s;
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


def search_actors(query: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """Kayıtlı aktörleri filtreler ve sayfalar (FTS / trigram uyumlu)."""
    q_str = f"%{query.strip()}%" if query.strip() else "%"
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) as total
            FROM entities
            WHERE entity_type IN ('person', 'institution')
              AND canonical_name ILIKE %s;
            """,
            (q_str,),
        )
        row = cur.fetchone()
        total = int(row["total"]) if row else 0

        cur.execute(
            """
            SELECT id, canonical_name as name, entity_type, is_key_entity
            FROM entities
            WHERE entity_type IN ('person', 'institution')
              AND canonical_name ILIKE %s
            ORDER BY is_key_entity DESC, canonical_name ASC
            LIMIT %s OFFSET %s;
            """,
            (q_str, limit, offset),
        )
        actors = [dict(r) for r in cur.fetchall()]

    return {
        "actors": actors,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + len(actors)) < total,
    }


def search_accountability(
    query: str = "",
    status_filter: str = "all",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Hesap Sor kayıtlarını sunucu tarafında filtreler ve sayfalar."""
    q_str = f"%{query.strip()}%" if query.strip() else "%"

    # Durum filtresi koşulu
    status_clause = ""
    status_params: list[Any] = []
    if status_filter == "verified":
        status_clause = "AND r.status = 'verified'"
    elif status_filter == "supported":
        status_clause = "AND r.status = 'supported'"
    elif status_filter == "contra":
        status_clause = "AND r.relation IN ('contradicts', 'fails')"
    elif status_filter == "inferred":
        status_clause = "AND (r.status = 'inferred' OR r.status = 'unresolved')"

    with connection() as conn, conn.cursor() as cur:
        count_sql = f"""
            SELECT count(*) as total
            FROM claims c
            JOIN events e ON e.id = c.event_id
            LEFT JOIN event_relations r ON r.from_event_id = e.id
                 AND r.relation IN ('fulfils', 'fails', 'contradicts')
            WHERE c.claim_type = 'promise'
              AND (c.claim_text ILIKE %s OR e.title ILIKE %s)
              {status_clause};
        """
        cur.execute(count_sql, [q_str, q_str, *status_params])
        count_row = cur.fetchone()
        total = int(count_row["total"]) if count_row else 0

        data_sql = f"""
            SELECT c.id as claim_id, c.claim_text, c.evidence_status, c.event_id,
                   e.title as event_title, e.first_reported_at,
                   c.status_reason,
                   r.relation as outcome_relation,
                   r.status as relation_status,
                   r.evidence_payload as evidence_payload
            FROM claims c
            JOIN events e ON e.id = c.event_id
            LEFT JOIN event_relations r ON r.from_event_id = e.id
                 AND r.relation IN ('fulfils', 'fails', 'contradicts')
            WHERE c.claim_type = 'promise'
              AND (c.claim_text ILIKE %s OR e.title ILIKE %s)
              {status_clause}
            ORDER BY e.first_reported_at DESC
            LIMIT %s OFFSET %s;
        """
        cur.execute(data_sql, [q_str, q_str, *status_params, limit, offset])
        out = []
        for r in cur.fetchall():
            reported = r["first_reported_at"].isoformat() if r["first_reported_at"] else ""
            status_reason = r.get("status_reason") or {}
            out.append(
                {
                    "claim_id": r["claim_id"],
                    "event_title": r["event_title"],
                    "promise_text": r["claim_text"],
                    "speaker": status_reason.get("speaker", "Bilinmeyen Aktör")
                    if isinstance(status_reason, dict)
                    else "Bilinmeyen Aktör",
                    "reported_at": reported,
                    "status": r["outcome_relation"] or "pending",
                    "relation_status": r.get("relation_status") or "unresolved",
                    "evidence_status": r["evidence_status"],
                    "evidence_payload": r.get("evidence_payload") or {},
                }
            )

    return {
        "items": out,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + len(out)) < total,
    }


def get_actor_stance_shifts(actor_name: str) -> list[dict[str, Any]]:
    """Belirli bir aktöre ait söylem değişikliklerini ve zıtlıkları döndürür."""
    from politikdesk.political_memory.stance_shift import detect_stance_shifts_from_memory

    mem = get_actor_memory(actor_name)
    shifts = detect_stance_shifts_from_memory(mem)
    return [s.to_dict() for s in shifts]


def list_all_stance_shifts(limit: int = 50) -> list[dict[str, Any]]:
    """Tüm aktörler üzerinden tespit edilen söylem değişikliklerini listeler."""
    from politikdesk.political_memory.stance_shift import detect_stance_shifts_from_memory

    actors_res = search_actors(query="", limit=20)
    all_shifts: list[dict[str, Any]] = []

    for item in actors_res.get("actors", []):
        name = item.get("name")
        if name:
            mem = get_actor_memory(name)
            shifts = detect_stance_shifts_from_memory(mem)
            all_shifts.extend([s.to_dict() for s in shifts])

    all_shifts.sort(key=lambda s: s.get("earlier_date") or "", reverse=True)
    return all_shifts[:limit]


