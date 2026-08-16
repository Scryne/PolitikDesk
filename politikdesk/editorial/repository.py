"""Editoryal katmanın veritabanı erişimi (F3-10, F3-14).

Karar mantığı saf tutulur (`generator.py`, `checker.py`, `guards.py` DB'ye
dokunmaz); okuma/yazma buradadır. Aynı ayrım Faz 2'de `clustering`
tarafında da yapıldı ve F2-14'ün 15 eşik denemesini mümkün kılan şeydi.
"""

from __future__ import annotations

import json
from typing import Any

from politikdesk.db import connection, fetch_one
from politikdesk.editorial.guards import ClaimForGeneration
from politikdesk.observability import get_logger

log = get_logger(__name__)


def load_claims_for_generation(event_id: int) -> list[ClaimForGeneration]:
    """Olayın iddialarını ve kanıt bağlarını üretim biçiminde okur.

    Sıra kararlıdır (durum gücü, sonra kimlik): aynı olay iki kez
    üretilirse prompt aynı olsun ki kalite farkı modele atfedilebilsin.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id, c.claim_text, c.claim_type, c.evidence_status,
                   c.normalized_value, c.status_reason->>'rule' AS status_rule
            FROM claims c
            WHERE c.event_id = %s
            ORDER BY
              CASE c.evidence_status
                WHEN 'strongly_corroborated' THEN 0
                WHEN 'attribution_verified' THEN 1
                WHEN 'partially_corroborated' THEN 2
                WHEN 'contradicted' THEN 3
                WHEN 'single_source' THEN 4
                ELSE 5
              END,
              c.id
            """,
            (event_id,),
        )
        claim_rows = [dict(r) for r in cur.fetchall()]
        if not claim_rows:
            return []

        cur.execute(
            """
            SELECT ev.claim_id, ev.stance, ev.quote_span,
                   s.name AS source_name, s.slug AS source_slug,
                   s.tier, s.kind, s.independence_group,
                   a.canonical_url, a.published_at
            FROM evidence ev
            JOIN articles a ON a.id = ev.article_id
            JOIN sources s ON s.id = a.source_id
            WHERE ev.claim_id = ANY(%s)
            ORDER BY s.tier, ev.id
            """,
            ([r["id"] for r in claim_rows],),
        )
        evidence_by_claim: dict[int, list[dict[str, Any]]] = {}
        for row in cur.fetchall():
            evidence_by_claim.setdefault(row["claim_id"], []).append(dict(row))

    return [
        ClaimForGeneration(
            claim_id=row["id"],
            claim_text=row["claim_text"],
            claim_type=row["claim_type"],
            evidence_status=row["evidence_status"],
            status_rule=row["status_rule"] or "",
            normalized_value=row["normalized_value"],
            evidence=tuple(evidence_by_claim.get(row["id"], ())),
        )
        for row in claim_rows
    ]


def event_header(event_id: int) -> dict[str, Any] | None:
    """Olayın üretimde DEĞİL, ekranda gösterilecek başlık bilgisi."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, status, salience_score, article_count,
                   independent_count, has_primary_source, first_reported_at,
                   last_update_at, review_flag
            FROM events WHERE id = %s AND merged_into_id IS NULL
            """,
            (event_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def save_draft(
    *,
    user_id: int,
    event_id: int,
    angle: str,
    body: str,
    cited_claim_ids: list[int],
    grounding_result: dict[str, Any],
    is_grounded: bool,
    model: str,
    prompt_version: str,
    check_result: dict[str, Any] | None = None,
) -> int:
    """Taslağı kaydeder ve kimliğini döndürür.

    Grounding'i düşen taslak da KAYDEDİLİR. Silmek, kapı G3 koşul 2'nin
    ("kanıtta olmayan sayı/tarih %0") paydasını yok etmek olurdu: yalnızca
    hayatta kalanları saymak oranı her zaman %0 gösterir.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO drafts (
                user_id, event_id, angle, body, cited_claim_ids,
                grounding_result, is_grounded, check_result, model, prompt_version
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s)
            RETURNING id
            """,
            (
                user_id,
                event_id,
                angle,
                body,
                cited_claim_ids,
                json.dumps(grounding_result, ensure_ascii=False),
                is_grounded,
                json.dumps(check_result, ensure_ascii=False) if check_result else None,
                model,
                prompt_version,
            ),
        )
        draft_id = int(fetch_one(cur)["id"])
        conn.commit()

    log.info("draft_saved", draft_id=draft_id, event_id=event_id, angle=angle, grounded=is_grounded)
    return draft_id


def get_draft(draft_id: int) -> dict[str, Any] | None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.*, e.title AS event_title
            FROM drafts d JOIN events e ON e.id = d.event_id
            WHERE d.id = %s
            """,
            (draft_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def list_drafts(event_id: int, limit: int = 20) -> list[dict[str, Any]]:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, angle, body, cited_claim_ids, is_grounded, grounding_result,
                   check_result, user_action, final_body, edit_distance,
                   model, prompt_version, created_at, action_at
            FROM drafts WHERE event_id = %s
            ORDER BY created_at DESC LIMIT %s
            """,
            (event_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def store_check_result(draft_id: int, check_result: dict[str, Any]) -> None:
    """Pre-publish check çıktısını taslağa iliştirir (F3-13)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE drafts SET check_result = %s::jsonb WHERE id = %s",
            (json.dumps(check_result, ensure_ascii=False), draft_id),
        )
        conn.commit()


def record_action(
    draft_id: int, action: str, final_body: str | None, edit_distance: float | None
) -> dict[str, Any]:
    """Kullanıcı aksiyonunu ve düzenleme mesafesini yazar (F3-14).

    `audit_log`'a da düşer: taslak aksiyonları ürün metriğinin ham
    verisidir (draft acceptance rate, edit distance — Spec §13.3).
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE drafts
            SET user_action = %s, final_body = %s, edit_distance = %s, action_at = now()
            WHERE id = %s
            RETURNING id, event_id, user_id, angle, user_action, edit_distance
            """,
            (action, final_body, edit_distance, draft_id),
        )
        row = fetch_one(cur)
        cur.execute(
            """
            INSERT INTO audit_log (actor, action, target, payload)
            VALUES (%s, 'draft_action', %s, %s::jsonb)
            """,
            (
                f"user:{row['user_id']}",
                f"drafts/{draft_id}",
                json.dumps(
                    {"action": action, "edit_distance": edit_distance},
                    ensure_ascii=False,
                ),
            ),
        )
        conn.commit()
    return dict(row)
