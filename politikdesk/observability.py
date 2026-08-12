"""Gözlemlenebilirlik temeli — structured log + Sentry (F0-18).

DoD: bir hata Sentry'de görünüyor; log JSON formatında.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from politikdesk.config import Settings, get_settings

_configured = False


def configure_logging(settings: Settings | None = None) -> None:
    """structlog'u JSON (üretim) veya renkli konsol (geliştirme) çıktısına bağlar."""
    global _configured
    settings = settings or get_settings()

    # force=True: yapılandırma idempotent olsun. Aksi halde root logger'da
    # zaten bir handler varsa (uvicorn, pytest) basicConfig sessizce hiçbir
    # şey yapmaz ve loglar beklenen biçimde çıkmaz.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        force=True,
    )

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        # Önbellek kapalı: yeniden yapılandırma (test, env değişimi) anında etkili olsun.
        cache_logger_on_first_use=False,
    )
    _configured = True


def configure_sentry(settings: Settings | None = None) -> bool:
    """Sentry'yi başlatır. DSN yoksa sessizce atlar ve False döner."""
    settings = settings or get_settings()
    if not settings.sentry_dsn:
        return False

    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        # KVKK: kişisel veri varsayılan olarak gönderilmez.
        send_default_pii=False,
    )
    return True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)
