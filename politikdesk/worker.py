"""Celery uygulaması (F0-12 iskelet, F1-05'te doldurulur).

Spec §11.1: Redis + Celery. Ingestion, embedding, kümeleme ve LLM
çağrıları arka planda; UI hiçbir zaman bloklanmaz.
"""

from __future__ import annotations

from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown

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


@worker_process_init.connect
def on_worker_process_init(**kwargs: object) -> None:
    """Celery pre-fork alt süreci başladığında DB bağlantı havuzunu sıfırlar."""
    from politikdesk.db import reset_db_pool

    reset_db_pool()


@worker_process_shutdown.connect
def on_worker_process_shutdown(**kwargs: object) -> None:
    """Celery pre-fork alt süreci kapandığında havuzu temiz kapatır."""
    from politikdesk.db import reset_db_pool

    reset_db_pool()

