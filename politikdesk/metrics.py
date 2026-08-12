"""Metrik kaydı — `metrics` tablosuna yazar (F0-18, Spec §13.3).

Faz 3'te (F3-19) sekiz ürün metriğinin tamamı buradan geçer. Faz 0'da
altyapı hazır ve test edilebilir durumda.
"""

from __future__ import annotations

import json
from typing import Any, Final

from politikdesk.db import connection
from politikdesk.observability import get_logger

log = get_logger(__name__)

# Spec §13.3 — MVP'de izlenecek sekiz ürün metriği.
PRODUCT_METRICS: Final[frozenset[str]] = frozenset(
    {
        "time_to_understanding",
        "draft_acceptance_rate",
        "edit_distance",
        "diversity_ratio",
        "briefing_open_rate",
        "daily_active_minutes",
        "correction_rate",
        "cost_per_active_user",
    }
)


def record(
    metric_name: str,
    value: float,
    *,
    user_id: int | None = None,
    dimensions: dict[str, Any] | None = None,
) -> None:
    """Tek bir metrik ölçümünü kalıcı olarak kaydeder.

    Metrik yazımı asla çağıran akışı düşürmez: hata loglanır, yutulur.
    """
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO metrics (metric_name, metric_value, user_id, dimensions)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (metric_name, float(value), user_id, json.dumps(dimensions or {})),
            )
            conn.commit()
    except Exception:  # noqa: BLE001 — metrik kaybı ürünü durdurmaz
        log.warning("metric_write_failed", metric_name=metric_name, exc_info=True)
