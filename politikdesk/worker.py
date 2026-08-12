"""Celery uygulaması (F0-12 iskelet, F1-05'te doldurulur).

Spec §11.1: Redis + Celery. Ingestion, embedding, kümeleme ve LLM
çağrıları arka planda; UI hiçbir zaman bloklanmaz.
"""

from __future__ import annotations

from celery import Celery

from politikdesk.config import get_settings
from politikdesk.observability import configure_logging

settings = get_settings()
configure_logging(settings)

app = Celery(
    "politikdesk",
    broker=settings.redis_url,
    backend=settings.redis_url,
    # `include` ZORUNLU: olmadan worker yalnızca bu dosyadaki görevleri görür
    # ve beat_schedule (tasks.py içinde tanımlı) hiç yüklenmez.
    include=["politikdesk.tasks"],
)
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Faz 1'de eklenecek zamanlanmış görevler (F1-05 / F1-12):
#   app.conf.beat_schedule = {
#       "ingest-every-5-minutes": {...},
#       "purge-expired-bodies-daily": {...},
#   }


@app.task(name="politikdesk.ping")
def ping() -> str:
    """Worker'ın ayakta olduğunu doğrulayan en küçük görev."""
    return "pong"
