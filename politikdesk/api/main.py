"""FastAPI uygulaması (F0-12).

Faz 0'da yalnızca sağlık uçları var — `docker compose up` ile tüm
servislerin ayağa kalktığı G0 koşulunu doğrulanabilir kılmak için.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from politikdesk import __version__
from politikdesk.admin.calendar import router as admin_calendar_router
from politikdesk.admin.events import router as admin_events_router
from politikdesk.admin.router import router as admin_router
from politikdesk.api.ingest import router as ingest_router
from politikdesk.config import get_settings
from politikdesk.observability import configure_logging, configure_sentry, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201, ARG001
    settings = get_settings()
    configure_logging(settings)
    sentry_on = configure_sentry(settings)
    log.info("api_started", env=settings.env, version=__version__, sentry=sentry_on)
    yield
    log.info("api_stopped")


app = FastAPI(
    title="PolitikDesk API",
    version=__version__,
    description="Makro ekonomi gündemi için kanıt temelli editoryal çalışma masası.",
    lifespan=lifespan,
)

# Faz 1 router'ları
app.include_router(admin_router)
app.include_router(admin_events_router)
app.include_router(admin_calendar_router)
app.include_router(ingest_router)


@app.get("/health/live", tags=["health"])
def live() -> dict[str, Any]:
    """Süreç ayakta mı? Bağımlılık kontrolü yapmaz."""
    return {"status": "ok", "version": __version__}


@app.get("/health/ready", tags=["health"])
def ready() -> JSONResponse:
    """Bağımlılıklar (Postgres, Redis) erişilebilir mi?"""
    checks: dict[str, bool] = {}

    try:
        from politikdesk.db import ping

        checks["postgres"] = ping()
    except Exception:  # noqa: BLE001
        log.warning("healthcheck_postgres_failed", exc_info=True)
        checks["postgres"] = False

    try:
        import redis

        checks["redis"] = bool(redis.from_url(get_settings().redis_url).ping())
    except Exception:  # noqa: BLE001
        log.warning("healthcheck_redis_failed", exc_info=True)
        checks["redis"] = False

    healthy = all(checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )
