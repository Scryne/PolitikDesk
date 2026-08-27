"""Celery Dead-Letter Queue (DLQ) ve Otomatik Onarım Katmanı.

Tüm denemeleri tükenen veya kritik hata alan Celery arka plan görevlerini
veritabanında yakalar; operatöre admin panelinden inceleme, yeniden kuyruğa
atma (self-healing) veya arşivleme imkanı sunar.
"""

from __future__ import annotations

import json
from typing import Any

from politikdesk.db import connection
from politikdesk.observability import get_logger

log = get_logger(__name__)


def record_dead_letter_task(
    *,
    task_id: str,
    task_name: str,
    args: list[Any] | tuple[Any, ...] | None = None,
    kwargs: dict[str, Any] | None = None,
    exception: BaseException | str | None = None,
    traceback_str: str = "",
    retry_count: int = 0,
) -> int:
    """Başarısız görevi DLQ tablosuna kaydeder."""
    safe_args = json.dumps(list(args or []), default=str, ensure_ascii=False)
    safe_kwargs = json.dumps(dict(kwargs or {}), default=str, ensure_ascii=False)
    exc_type = type(exception).__name__ if isinstance(exception, BaseException) else "Exception"
    exc_msg = str(exception or "Bilinmeyen hata")

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dead_letter_tasks (
                task_id, task_name, args, kwargs, exception_type,
                exception_message, traceback, retry_count, status, created_at
            )
            VALUES (%s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, 'pending', now())
            RETURNING id
            """,
            (
                task_id,
                task_name,
                safe_args,
                safe_kwargs,
                exc_type,
                exc_msg,
                traceback_str or "",
                retry_count,
            ),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError("DLQ kaydı eklenemedi.")
        entry_id = int(row["id"])
        conn.commit()

    log.error(
        "dlq_task_recorded",
        entry_id=entry_id,
        task_id=task_id,
        task_name=task_name,
        exc_type=exc_type,
    )
    return entry_id


def list_dead_letter_tasks(
    limit: int = 50,
    status: str | None = "pending",
) -> list[dict[str, Any]]:
    """DLQ kayıtlarını listeler."""
    with connection() as conn, conn.cursor() as cur:
        if status and status != "all":
            cur.execute(
                """
                SELECT id, task_id, task_name, args, kwargs, exception_type,
                       exception_message, traceback, retry_count, status,
                       created_at, resolved_at
                FROM dead_letter_tasks
                WHERE status = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (status, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, task_id, task_name, args, kwargs, exception_type,
                       exception_message, traceback, retry_count, status,
                       created_at, resolved_at
                FROM dead_letter_tasks
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def get_dlq_summary() -> dict[str, int]:
    """DLQ durum özeti sayılarını döner."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                count(*) FILTER (WHERE status = 'pending') AS pending_count,
                count(*) FILTER (WHERE status = 'retried') AS retried_count,
                count(*) FILTER (WHERE status = 'discarded') AS discarded_count,
                count(*) AS total_count
            FROM dead_letter_tasks
            """
        )
        row = cur.fetchone()
        if not row:
            return {"pending": 0, "retried": 0, "discarded": 0, "total": 0}
        return {
            "pending": int(row["pending_count"] or 0),
            "retried": int(row["retried_count"] or 0),
            "discarded": int(row["discarded_count"] or 0),
            "total": int(row["total_count"] or 0),
        }


def requeue_dead_letter_task(entry_id: int) -> bool:
    """Bir görevi Celery kuyruğuna yeniden iletir ve durumunu günceller."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT task_name, args, kwargs
            FROM dead_letter_tasks
            WHERE id = %s AND status = 'pending'
            """,
            (entry_id,),
        )
        row = cur.fetchone()
        if not row:
            return False

        task_name = row["task_name"]
        args = row["args"] if isinstance(row["args"], list) else []
        kwargs = row["kwargs"] if isinstance(row["kwargs"], dict) else {}

        # Celery uygulaması üzerinden görevi asenkron yeniden tetikle
        from politikdesk.worker import app as celery_app

        celery_app.send_task(task_name, args=args, kwargs=kwargs)

        cur.execute(
            """
            UPDATE dead_letter_tasks
            SET status = 'retried', resolved_at = now()
            WHERE id = %s
            """,
            (entry_id,),
        )
        conn.commit()

    log.info("dlq_task_requeued", entry_id=entry_id, task_name=task_name)
    return True


def discard_dead_letter_task(entry_id: int) -> bool:
    """Görevi arşivlendi/yoksayıldı olarak işaretler."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE dead_letter_tasks
            SET status = 'discarded', resolved_at = now()
            WHERE id = %s
            """,
            (entry_id,),
        )
        conn.commit()
    log.info("dlq_task_discarded", entry_id=entry_id)
    return True


def retry_all_pending(limit: int = 50) -> int:
    """Tüm bekleyen DLQ görevlerini topluca yeniden kuyruğa atar."""
    tasks = list_dead_letter_tasks(limit=limit, status="pending")
    requeued = 0
    for t in tasks:
        if requeue_dead_letter_task(int(t["id"])):
            requeued += 1
    return requeued
