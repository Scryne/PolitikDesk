"""Celery uygulaması (F0-12 iskelet, F1-05'te doldurulur).

Spec §11.1: Redis + Celery. Ingestion, embedding, kümeleme ve LLM
çağrıları arka planda; UI hiçbir zaman bloklanmaz.
"""

from __future__ import annotations

from celery import Celery
from celery.signals import task_failure, worker_process_init, worker_process_shutdown

from politikdesk.config import get_settings
from politikdesk.observability import configure_logging, get_logger

settings = get_settings()
configure_logging(settings)
log = get_logger(__name__)

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
    # ── Zaman sınırı: KÜRESEL VARSAYILAN (20 Ağustos 2026 denetimi) ──
    #
    # Eskiden yalnızca iki görevin kendi sınırı vardı; geri kalan on altısı
    # sınırsızdı. Worker `--concurrency 2` ile koşuyor, yani asılı kalan iki
    # görev TÜM işleme kapasitesini süresiz olarak tutabilirdi ve beat
    # kuyruğa yeni iş yığmaya devam ederdi. Boru hattı, hiçbir şey "hata"
    # vermeden durur — 13 Ağustos'ta kümelemenin 13 saat sessizce durması
    # tam olarak bu sınıftan bir arızaydı.
    #
    # `soft` önce gelir: görev `SoftTimeLimitExceeded` alır, kendi `except`
    # bloğu çalışır ve düzgün bir hata kaydı düşer. `hard` yalnızca soft'a
    # yanıt vermeyen (C içinde bloke, ölü soket) süreçleri keser.
    #
    # Kendi sınırını bildiren görevler (`ingest_social`, `link_political_
    # relations`, `sync_stance_shifts`) bu varsayılanı EZER; dekoratördeki
    # değer önceliklidir.
    task_soft_time_limit=600,
    task_time_limit=900,
    # Worker çökerse görev yeniden teslim edilsin (`acks_late` ile birlikte
    # anlamlıdır: onay iş bitince verilir, çöken worker'ın işi kaybolmaz).
    task_reject_on_worker_lost=True,
    # ── Kuyruk ayrımı: yavaş LLM işi hızlı işi AÇLIĞA düşürmesin ──
    #
    # 20 Ağustos 2026 denetiminde ölçüldü: "Tarihsel bağlam" aşaması
    # 16,8 saatlik birikmeyle KIRMIZIYA döndü, oysa görev elle
    # çalıştırıldığında 35 olayı saniyeler içinde bitirdi. Kod arızası
    # yoktu; beat görevi düzenli gönderiyordu. Sorun kuyruktaydı:
    #
    #   worker `--concurrency 2` ile koşuyor ve iddia çıkarımı çağrıları
    #   6–100 saniye sürüyor (sağlayıcı 429 verince fallback'e düşüyor).
    #   İki slot da LLM'e gidince, saniyeler süren SAF VERİTABANI
    #   görevleri (bağlam, siyasi ilişkiler) sırada bekliyordu.
    #
    # ⛔ Bu, eşzamanlılık artırma DEĞİLDİR. `docker-compose.yml`'de
    # ölçülüp yazıldığı gibi darboğaz worker değil ücretsiz katman
    # kotasıdır (2→4 eşzamanlılık: verim sabit, gecikme +%40). Buradaki
    # ayrım LLM çağrı hızını ARTIRMAZ — `llm` kuyruğu yine iki slotla
    # koşar. Yalnızca LLM olmayan işin o slotları beklemesini önler.
    task_routes={
        "politikdesk.extract_claims_pending": {"queue": "llm"},
        "politikdesk.generate_briefing": {"queue": "llm"},
    },
    # Yönlendirilmeyen her görev buraya düşer.
    task_default_queue="celery",
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


@task_failure.connect
def on_task_failure(
    sender: object = None,
    task_id: str | None = None,
    exception: BaseException | None = None,
    args: tuple[object, ...] | None = None,
    kwargs: dict[str, object] | None = None,
    traceback: object = None,
    einfo: object = None,
    **other: object,
) -> None:
    """Celery görevi başarısız olduğunda DLQ tablosuna kaydeder ve SRE uyarısı gönderir."""
    task_name = getattr(sender, "name", str(sender))
    tb_str = str(getattr(einfo, "traceback", None) or traceback or "")

    try:
        from politikdesk.dlq import record_dead_letter_task

        record_dead_letter_task(
            task_id=task_id or "unknown",
            task_name=task_name,
            args=list(args or ()),
            kwargs=dict(kwargs or {}),
            exception=exception,
            traceback_str=tb_str,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("dlq_recording_failed", error=str(exc))

    try:
        from politikdesk.sre_alerts import send_alert_notification

        send_alert_notification(
            title=f"Celery Görev Hatası: {task_name}",
            detail=f"Görev hatası: {str(exception)[:300]}",
            severity="CRITICAL",
            source="celery_worker",
            action="/admin/ üzerinden DLQ inceleyin veya loglara bakın",
        )
    except Exception:
        pass

