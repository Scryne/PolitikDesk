"""Gözlemlenebilirlik temeli — structured log + Sentry (F0-18).

DoD: bir hata Sentry'de görünüyor; log JSON formatında.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, cast

import structlog

from politikdesk.config import Settings, get_settings

_configured = False

_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "token",
        "access_token",
        "refresh_token",
        "api_token",
        "authorization",
        "cookie",
        "secret",
        "private_key",
        "credential",
        "credentials",
    }
)


def _is_sensitive_key(key: object) -> bool:
    kl = str(key).lower()
    return any(s in kl for s in _SENSITIVE_KEYS)


def _redact_value(val: Any) -> Any:
    if isinstance(val, dict):
        return {
            k: "[REDACTED]" if _is_sensitive_key(k) else _redact_value(v)
            for k, v in val.items()
        }
    if isinstance(val, (list, tuple)):
        redacted_list = [_redact_value(item) for item in val]
        return type(val)(redacted_list) if isinstance(val, tuple) else redacted_list
    return val


def redact_sensitive_keys(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Log boru hattında iç içe geçmiş veri yapılarındaki ve çerezlerdeki
    hassas anahtarları sansürler.
    """
    return cast(dict[str, Any], _redact_value(event_dict))


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
        redact_sensitive_keys,
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
