"""Otomatik Arka Plan Tweet Üretim ve Telegram İletim Servisi (Spec §12.4, §15).

Teyit zincirinden geçmiş ve yazıma hazır hale gelmiş gündem olaylarını otomatik
olarak tespit eder, editoryal kimlik profiline uygun X tweet taslağını LLM ile üretir,
halüsinasyon/grounding denetimlerinden geçirir ve kullanıcının Telegram hesabına
anlık olarak iletir.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from politikdesk.config import get_settings
from politikdesk.db import connection
from politikdesk.editorial import repository as ed_repo
from politikdesk.editorial import service
from politikdesk.editorial.guards import GenerationBlocked
from politikdesk.observability import get_logger
from politikdesk.telegram_notifier import send_draft_notification

log = get_logger(__name__)


def find_pending_auto_draft_events(
    limit: int = 5,
    min_salience: int = 30,
    max_hours: int = 48,
) -> list[dict[str, Any]]:
    """Henüz taslağı üretilmemiş, teyitli iddiaları bulunan uygun olayları getirir."""
    sql = """
        SELECT e.id, e.title, e.status, e.salience_score,
               e.created_at, e.last_update_at,
               (SELECT count(*) FROM articles a WHERE a.event_id = e.id) AS article_count,
               (SELECT count(*) FROM claims c WHERE c.event_id = e.id) AS claim_count
        FROM events e
        WHERE e.merged_into_id IS NULL
          AND e.salience_score >= %s
          AND e.last_update_at >= now() - make_interval(hours => %s)
          AND NOT EXISTS (
              SELECT 1 FROM drafts d WHERE d.event_id = e.id
          )
          AND EXISTS (
              SELECT 1 FROM claims c 
              WHERE c.event_id = e.id 
                AND c.evidence_status IN ('strongly_corroborated', 'partially_corroborated')
          )
        ORDER BY e.salience_score DESC, e.last_update_at DESC
        LIMIT %s;
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (min_salience, max_hours, limit))
        return list(cur.fetchall())


def process_pending_auto_drafts(
    limit: int | None = None,
    angle: str | None = None,
    user_id: int = 1,
    client: Any | None = None,
) -> dict[str, Any]:
    """Bekleyen tüm teyitli olaylar için otomatik taslak üretimi ve bildirim akışını yürütür."""
    settings = get_settings()

    if not settings.auto_draft_enabled:
        log.debug("auto_draft_disabled")
        return {"processed": 0, "drafts_created": 0, "telegram_sent": 0, "status": "disabled"}

    batch_limit = limit or settings.auto_draft_max_events_per_cycle
    target_angle = angle or settings.auto_draft_angle
    min_salience = settings.auto_draft_min_salience

    eligible_events = find_pending_auto_draft_events(
        limit=batch_limit,
        min_salience=min_salience,
    )

    if not eligible_events:
        return {"processed": 0, "drafts_created": 0, "telegram_sent": 0}

    drafts_created = 0
    telegram_sent = 0
    errors = 0

    for event in eligible_events:
        event_id = event["id"]
        try:
            # 1. Üretilebilirlik denetimi
            can_gen = service.can_generate(event_id)
            if not can_gen.get("allowed", False):
                log.debug(
                    "auto_draft_event_not_allowed",
                    event_id=event_id,
                    reason=can_gen.get("reason"),
                )
                continue

            # 2. Taslak üretimi (Grounding, pre-publish check ve kayıt dahil)
            payload = service.generate_for_event(
                event_id=event_id,
                angle=target_angle,
                user_id=user_id,
                client=client,
                persist=True,
            )

            draft_id = payload.get("draft_id")
            if not draft_id:
                continue

            drafts_created += 1
            log.info(
                "auto_draft_created",
                event_id=event_id,
                draft_id=draft_id,
                angle=target_angle,
            )

            # 3. Telegram Bildirimi
            has_tg = bool(settings.telegram_bot_token and settings.telegram_chat_id)
            if settings.telegram_notify_drafts and has_tg:
                raw_claims = ed_repo.load_claims_for_generation(event_id)
                claims_dicts: list[dict[str, Any]] = [
                    asdict(c) if is_dataclass(c) else c.as_dict() if hasattr(c, "as_dict") else {}
                    for c in raw_claims
                ]
                sent = send_draft_notification(
                    event=event,
                    draft={"id": draft_id, "body": payload.get("body", "")},
                    claims=claims_dicts,
                )
                if sent:
                    telegram_sent += 1

        except GenerationBlocked as exc:
            log.warning("auto_draft_generation_blocked", event_id=event_id, reason=str(exc))
        except Exception as exc:  # noqa: BLE001
            errors += 1
            log.error(
                "auto_draft_failed_for_event",
                event_id=event_id,
                error=str(exc),
                exc_info=True,
            )

    return {
        "processed": len(eligible_events),
        "drafts_created": drafts_created,
        "telegram_sent": telegram_sent,
        "errors": errors,
    }
