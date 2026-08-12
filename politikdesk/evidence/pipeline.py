"""Kanıt durumu ve salience hesaplama turu (F2-12, F2-13, F2-15 orkestrasyonu).

Spec §11.3 adım 7: bağımsız sayım → R0–R7 → `evidence_status` +
`status_reason`, ardından olay skoru.

⛔ Bu modül `politikdesk.llm` import EDEMEZ (Spec §11.2). Yalnızca
veritabanından okur, deterministik hesaplar, geri yazar.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from politikdesk.db import connection
from politikdesk.evidence.independence import EvidenceArticle
from politikdesk.evidence.rules import Claim, Evidence, compute_status
from politikdesk.evidence.salience import EventSignals, global_salience
from politikdesk.observability import get_logger

log = get_logger(__name__)

VELOCITY_WINDOW_MINUTES = 60  # Spec §8.4: "ilk 60 dk içindeki makale sayısı"


@dataclass
class EvidenceStats:
    claims_scored: int = 0
    events_scored: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "claims_scored": self.claims_scored,
            "events_scored": self.events_scored,
            "errors": self.errors,
        }


def _parse_vector(literal: str | None) -> list[float]:
    if not literal:
        return []
    return [float(x) for x in literal.strip("[]").split(",") if x]


def _load_evidence(cur: Any, claim_id: int) -> list[Evidence]:
    cur.execute(
        """
        SELECT ev.stance, ev.quote_span,
               a.id AS article_id, a.simhash, a.independence_key,
               a.embedding::text AS embedding, a.title, a.excerpt,
               s.slug AS source_slug, s.tier, s.kind, s.independence_group
        FROM evidence ev
        JOIN articles a ON a.id = ev.article_id
        JOIN sources s ON s.id = a.source_id
        WHERE ev.claim_id = %s
        """,
        (claim_id,),
    )
    out: list[Evidence] = []
    for r in cur.fetchall():
        out.append(
            Evidence(
                article=EvidenceArticle(
                    article_id=r["article_id"],
                    source_slug=r["source_slug"],
                    tier=r["tier"],
                    kind=r["kind"],
                    independence_group=r["independence_group"],
                    simhash=r["simhash"] or 0,
                    embedding=_parse_vector(r["embedding"]),
                    text=" ".join(filter(None, (r["title"], r["excerpt"]))),
                ),
                stance=r["stance"],
                quote_span=r["quote_span"] or "",
            )
        )
    return out


def score_claims(limit: int = 200) -> int:
    """Durumu hesaplanmamış veya bayatlamış iddiaları puanlar."""
    scored = 0
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, claim_text, claim_type, normalized_value, event_id
            FROM claims
            WHERE status_reason IS NULL
               OR status_reason->>'engine_version' IS DISTINCT FROM %s
            ORDER BY id
            LIMIT %s
            """,
            ("evidence-engine@1.0.0", limit),
        )
        rows = list(cur.fetchall())

        for row in rows:
            evidence = _load_evidence(cur, row["id"])
            claim = Claim(
                claim_id=row["id"],
                claim_text=row["claim_text"],
                claim_type=row["claim_type"],
                normalized_value=row["normalized_value"],
                # R3, değerin kurumun yayın formatıyla doğrulandığını ister.
                # Bunu iddia çıkarımı işaretler; burada üretilmez.
                value_verified_against_source=bool(
                    (row["normalized_value"] or {}).get("verified_against_source")
                ),
            )
            result = compute_status(claim, evidence)
            cur.execute(
                """
                UPDATE claims
                SET evidence_status = %s, status_reason = %s::jsonb, computed_at = now()
                WHERE id = %s
                """,
                (result.status, json.dumps(result.reason, ensure_ascii=False), row["id"]),
            )
            scored += 1
        conn.commit()

    return scored


def _event_signals(cur: Any, event_id: int) -> EventSignals | None:
    cur.execute(
        """
        SELECT e.first_reported_at,
               (SELECT min(s.tier) FROM articles a JOIN sources s ON s.id = a.source_id
                 WHERE a.event_id = e.id) AS best_tier,
               (SELECT count(*) FROM articles a
                 WHERE a.event_id = e.id
                   AND COALESCE(a.published_at, a.first_seen_at)
                       <= e.first_reported_at + make_interval(mins => %s)) AS velocity,
               (SELECT count(*) > 0 FROM event_entities ee
                 JOIN entities en ON en.id = ee.entity_id
                 WHERE ee.event_id = e.id AND en.is_key_entity) AS has_key_entity,
               (SELECT bool_or(s.tier = 1) FROM articles a
                 JOIN sources s ON s.id = a.source_id WHERE a.event_id = e.id)
                 AS has_primary,
               (SELECT count(DISTINCT COALESCE(a.independence_key, s.slug))
                 FROM articles a JOIN sources s ON s.id = a.source_id
                 WHERE a.event_id = e.id) AS independent_count,
               (SELECT min(c.evidence_status) FROM claims c WHERE c.event_id = e.id)
                 AS weakest_status
        FROM events e WHERE e.id = %s
        """,
        (VELOCITY_WINDOW_MINUTES, event_id),
    )
    row = cur.fetchone()
    if row is None:
        return None

    return EventSignals(
        independent_count=row["independent_count"] or 0,
        has_primary_source=bool(row["has_primary"]),
        articles_in_first_hour=row["velocity"] or 0,
        best_tier=row["best_tier"] or 4,
        has_key_entity=bool(row["has_key_entity"]),
        evidence_status=row["weakest_status"] or "unverified",
        first_reported_at=row["first_reported_at"],
        now=datetime.now(UTC),
    )


def score_events(limit: int = 200) -> int:
    """Olayların global salience skorunu hesaplar ve yazar (F2-15).

    Yalnızca **global** kısım saklanır (0–90). Kişisel ayarlama feed
    sorgusunda hesaplanır ve buraya asla yazılmaz (Spec §8.4/B).
    """
    scored = 0
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM events
            WHERE merged_into_id IS NULL
            ORDER BY last_update_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        event_ids = [r["id"] for r in cur.fetchall()]

        for event_id in event_ids:
            signals = _event_signals(cur, event_id)
            if signals is None:
                continue
            breakdown = global_salience(signals)
            cur.execute(
                """
                UPDATE events
                SET salience_score = %s,
                    salience_breakdown = %s::jsonb,
                    independent_count = %s,
                    has_primary_source = %s
                WHERE id = %s
                """,
                (
                    breakdown.score,
                    json.dumps(breakdown.as_dict(), ensure_ascii=False),
                    signals.independent_count,
                    signals.has_primary_source,
                    event_id,
                ),
            )
            scored += 1
        conn.commit()

    return scored


def run(limit: int = 200) -> EvidenceStats:
    """Kanıt motoru turu: önce iddia durumları, sonra olay skorları.

    Sıra önemlidir: salience'ın cezası `evidence_status`'a bakar
    (Spec §8.4), o yüzden durumlar önce hesaplanır.
    """
    stats = EvidenceStats()
    try:
        stats.claims_scored = score_claims(limit)
        stats.events_scored = score_events(limit)
    except Exception as exc:  # noqa: BLE001
        stats.errors += 1
        log.error("evidence_run_failed", error=type(exc).__name__, detail=str(exc)[:300])
        raise

    log.info("evidence_run_complete", **stats.as_dict())
    return stats
