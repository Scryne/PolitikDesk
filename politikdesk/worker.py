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
    timezone=settings.timezone,
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@app.task(name="politikdesk.ping")
def ping() -> str:
    """Worker'ın ayakta olduğunu doğrulayan en küçük görev."""
    return "pong"


# Celery Beat başlatıldığında `politikdesk.worker.app` üzerinden yüklendiği için
# `tasks.py` içindeki görevler ve `app.conf.beat_schedule` burada zorunlu olarak yüklenir.
import politikdesk.tasks as _tasks  # noqa: F401, E402

