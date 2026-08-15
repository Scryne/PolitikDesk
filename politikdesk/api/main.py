"""FastAPI uygulaması (F0-12).

Faz 0'da yalnızca sağlık uçları var — `docker compose up` ile tüm
servislerin ayağa kalktığı G0 koşulunu doğrulanabilir kılmak için.
"""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from politikdesk import __version__
from politikdesk.admin.calendar import router as admin_calendar_router
from politikdesk.admin.events import router as admin_events_router
from politikdesk.admin.router import router as admin_router
from politikdesk.api.ingest import router as ingest_router
from politikdesk.config import get_settings
from politikdesk.observability import configure_logging, configure_sentry, get_logger
from politikdesk.web.accountability_view import router as accountability_router
from politikdesk.web.api import router as web_api_router
from politikdesk.web.archive_view import router as archive_router
from politikdesk.web.briefing import router as briefing_router
from politikdesk.web.draft import router as draft_router
from politikdesk.web.event import router as event_router
from politikdesk.web.feed import router as feed_router
from politikdesk.web.memory_view import router as memory_router
from politikdesk.web.metrics_dashboard import router as metrics_router
from politikdesk.web.onboarding import router as onboarding_router
from politikdesk.web.promises_view import router as promises_router

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

# Arayüz varlıkları: kendi barındırdığımız woff2'ler (DESIGN.md Bölüm 6.1).
#
# Harici font CDN'i BRIEF kırmızı çizgisidir: üçüncü taraf isteği hem G3 #7
# (olay sayfası p95 < 1,5 sn) için ekstra DNS+TLS gecikmesi, hem de arayüzün
# çalışması için dışarıya bağımlılık demek. Dosyalar `politikdesk/` içinde
# olduğu için `Dockerfile`'ın `COPY politikdesk ./politikdesk` satırıyla
# imaja giriyor — ayrı bir `COPY` gerekmiyor (bkz. tests/test_packaging.py).
#
# `immutable` güvenli: dosya adları içerik değişirse değişir (font sürümü
# yükseltilirse yeni dosya adı gelir).
_STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"
app.mount(
    "/static",
    StaticFiles(directory=_STATIC_DIR),
    name="static",
)

# Faz 1 router'ları
app.include_router(admin_router)
app.include_router(admin_events_router)
app.include_router(admin_calendar_router)
app.include_router(ingest_router)

# Faz 3 — arayüz ve editoryal katman.
# Sıra önemlidir: `event_router` "/event/{id}" gibi somut yolları,
# `feed_router` ise "/" kökünü tanımlar. FastAPI ilk eşleşeni kullanır.
app.include_router(feed_router)
app.include_router(event_router)
app.include_router(draft_router)
app.include_router(briefing_router)
app.include_router(onboarding_router)
app.include_router(metrics_router)
app.include_router(web_api_router)


# ─────────────────────────── kimlik doğrulama (I01 — denetim düzeltmesi)
#
# `PD_API_TOKEN` ayarlıysa tüm istekler bu belirteci taşımalıdır.
# Sağlık uçları (`/health/*`) ve statik varlıklar (`/static/*`) muaftır —
# Docker/K8s probları ve tarayıcı CSS/font istekleri belirteç taşımaz.
#
# Belirteç boşsa (varsayılan) middleware hiçbir şey yapmaz: geliştirme
# ortamında kimlik doğrulama gereksizdir ve eklenmesi mevcut akışları
# bozardı. Üretimde `.env`'ye `PD_API_TOKEN=<uzun-rastgele-dize>` yazmak
# yeterlidir.
_AUTH_EXEMPT = ("/health/", "/version", "/static/", "/favicon.ico", "/robots.txt")


class _TokenAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # noqa: ANN201
        token = get_settings().api_token
        if not token:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(prefix) for prefix in _AUTH_EXEMPT):
            return await call_next(request)

        # İki yol desteklenir: `Authorization: Bearer <token>` ve
        # `X-API-Token: <token>`. İkincisi programatik istemciler için
        # daha basittir (curl -H "X-API-Token: ...").
        provided = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            provided = auth_header[7:].strip()
        if not provided:
            provided = request.headers.get("x-api-token", "").strip() or None

        if provided is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Kimlik doğrulama gerekli. "
                         "Authorization: Bearer <token> veya "
                         "X-API-Token başlığı ekleyin."},
            )
        if not secrets.compare_digest(provided, token):
            return JSONResponse(
                status_code=403,
                content={"detail": "Geçersiz belirteç."},
            )
        return await call_next(request)


class _CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF koruması (I06 — denetim düzeltmesi).

    Tarayıcıdan gelen durum değiştiren (POST/PUT/DELETE/PATCH) isteklerde
    Origin/Referer başlığının sunucu adresiyle (Host) eşleştiğini doğrular.
    Farklı bir kaynaktan (cross-origin) gelen istekler 403 ile reddedilir.
    """

    _SAFE_METHODS = ("GET", "HEAD", "OPTIONS", "TRACE")

    async def dispatch(self, request: Request, call_next):  # noqa: ANN201
        if request.method in self._SAFE_METHODS:
            return await call_next(request)

        origin = request.headers.get("origin")
        referer = request.headers.get("referer")

        source = origin or referer
        if source:
            source_netloc = urlparse(source).netloc
            host = request.headers.get("host", "")
            if source_netloc and host and source_netloc != host:
                log.warning(
                    "csrf_origin_mismatch",
                    origin=source,
                    host=host,
                    path=request.url.path,
                )
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Cross-origin istek reddedildi (CSRF koruması)."},
                )

        return await call_next(request)


app.add_middleware(_CSRFProtectionMiddleware)
app.add_middleware(_TokenAuthMiddleware)


# ─────────────────────────────────────────── hata sayfaları (Bölüm 10.4)
#
# FastAPI'nin varsayılanı `{"detail": "..."}` JSON'ıdır. Bir API için doğru,
# bir EKRAN için değil: `/event/999999` yazan kullanıcı çıplak JSON görüyor
# ve geri dönüş yolu bulamıyordu (Bölüm 10.5: "404: geri dönüş yolu ver").
#
# Ayrım yola göre yapılır, `Accept` başlığına göre değil: `/api/*` her
# zaman JSON döner (JS uçları ona güvenir), gerisi HTML. Başlığa bakmak
# `fetch()`'in gönderdiği `*/*` yüzünden JS'e de HTML döndürürdü.
_ERROR_COPY: dict[int, tuple[str, str]] = {
    403: ("Bu sayfa için yetkin yok",
          "Erişim gerekiyorsa yönetici hesabından açılmalı."),
    404: ("Aradığın kayıt yok",
          "Adres yanlış olabilir ya da kayıt birleştirilmiş/silinmiş olabilir. "
          "Gündemden yeniden başlayabilirsin."),
    500: ("Bir şeyler ters gitti",
          "Sunucu bu isteği tamamlayamadı. Birkaç saniye sonra tekrar dene; "
          "sürerse boru hattı panosunda bir arıza görünüyor olabilir."),
}


def _wants_json(request: Request) -> bool:
    """JSON mı HTML mi?

    `/admin/` altında ikisi karışık: `/admin/metrics` bir EKRAN, ama
    `/admin/metrics/history` bir JSON ucu — yol kalıbıyla ayırmak
    (`/` ile bitiyor mu?) kırılgan olurdu ve yeni bir uç eklendiğinde
    sessizce yanlış tarafa düşerdi.

    Doğru ayrım istemcinin ne istediğidir: tarayıcı gezinmesi `Accept`
    başlığında `text/html` gönderir, `fetch()` `*/*` gönderir. `/api/*`
    her koşulda JSON döner — JS uçları buna güvenir ve bir gün tarayıcıda
    açılsalar bile sözleşmeleri değişmemeli.
    """
    if request.url.path.startswith("/api/"):
        return True
    return "text/html" not in request.headers.get("accept", "")


def _error_page(status: int, detail: str) -> HTMLResponse:
    from politikdesk.web.ui import button, error_state, page

    title, body = _ERROR_COPY.get(
        status, ("İstek tamamlanamadı", "Beklenmeyen bir durum oluştu.")
    )
    html = page(
        title,
        error_state(
            title,
            body,
            # Bölüm 10.4: ne oldu → neden → NASIL ÇÖZÜLÜR. Aksiyon şart.
            retry=button("Gündeme dön", href="/feed", variant="primary",
                         icon_name="arrow-left"),
            # Teknik ayrıntı küçük ve altta.
            code=f"HTTP {status} · {detail}" if detail else f"HTTP {status}",
        ),
        crumbs=((f"HTTP {status}", None),),
    )
    return HTMLResponse(html, status_code=status)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(  # noqa: RUF029
    request: Request, exc: StarletteHTTPException
) -> Response:
    if _wants_json(request):
        return JSONResponse(status_code=exc.status_code,
                            content={"detail": exc.detail})
    return _error_page(exc.status_code, str(exc.detail))


@app.get("/version", tags=["health"])
@app.get("/health/version", tags=["health"])
def version_endpoint() -> dict[str, Any]:
    """Sistem sürüm ve release identity bilgilerini döndürür (F1)."""
    from politikdesk.release import get_release_info

    return get_release_info().to_dict()


@app.get("/health/live", tags=["health"])
def live() -> dict[str, Any]:
    """Süreç ayakta mı? Bağımlılık kontrolü yapmaz."""
    from politikdesk.release import get_release_info

    rel = get_release_info(include_db_schema=False)
    return {
        "status": "ok",
        "version": rel.app_version,
        "git_sha": rel.git_sha,
        "env": rel.env,
    }


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
