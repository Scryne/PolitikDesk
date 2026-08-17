"""Vercel Serverless Entrypoint for PolitikDesk."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

# Ensure repo root is on sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from starlette.routing import Match  # noqa: E402

from politikdesk.api.main import app as fastapi_app  # noqa: E402


def _matches_any_route(path: str, method: str = "GET") -> bool:
    """FastAPI üzerinde kayıtlı bir rotanın tam veya kısmi eşleşip eşleşmediğini denetler."""
    test_scope = {"type": "http", "method": method, "path": path}
    for route in fastapi_app.router.routes:
        match, _ = route.matches(test_scope)
        if match in (Match.FULL, Match.PARTIAL):
            return True
    return False


def _resolve_request_path(scope: dict[str, Any]) -> str:
    """Vercel Serverless ve proxy ortamlarında asıl istemci yolunu çözer."""
    headers = dict(scope.get("headers", []))

    # 1. Reverse proxy / test ortamlarından gelen x-forwarded-uri
    if b"x-forwarded-uri" in headers:
        forwarded_str = headers[b"x-forwarded-uri"].decode("latin1")
        p = urlparse(forwarded_str).path
        if p and p not in ("/api/index.py", "/api/index", "/api"):
            return p if p.startswith("/") else "/" + p
        return "/"

    # 2. Rewrite query param (__path)
    raw_qs = scope.get("query_string", b"").decode("latin1")
    if raw_qs:
        qs_dict = parse_qs(raw_qs, keep_blank_values=True)
        if "__path" in qs_dict:
            injected = qs_dict.pop("__path")[0]
            # Route handler'larına __path sızmasın diye query string temizlenir
            new_qs = urlencode([(k, v) for k, vs in qs_dict.items() for v in vs])
            scope["query_string"] = new_qs.encode("latin1")
            if injected:
                return ("/" + injected.lstrip("/")) if injected != "/" else "/"

    # 3. Vercel Edge proxy başlığı (x-matched-path)
    if b"x-matched-path" in headers:
        matched = headers[b"x-matched-path"].decode("latin1")
        p = urlparse(matched).path
        if (
            p
            and p
            not in (
                "/api/index.py",
                "/api/index",
                "/api",
                "/api/index.py/",
                "/api/index/",
                "/api/",
            )
            and not p.startswith("/api/index")
        ):
            return p if p.startswith("/") else "/" + p

    # 4. Scope doğrudan path çözümleme
    raw_path = scope.get("path", "/")
    if not raw_path or raw_path in (
        "/api/index.py",
        "/api/index",
        "/api",
        "/api/",
        "/api/index/",
        "/api/index.py/",
    ):
        return "/"

    if raw_path.startswith("/api/index.py/"):
        cand = raw_path[len("/api/index.py") :]
        return cand or "/"

    if raw_path.startswith("/api/index/"):
        cand = raw_path[len("/api/index") :]
        return cand or "/"

    if raw_path.startswith("/api/api/"):
        return raw_path[4:]

    if raw_path.startswith("/api/"):
        method = scope.get("method", "GET")
        if _matches_any_route(raw_path, method):
            return raw_path
        stripped = raw_path[4:]
        return stripped or "/"

    return raw_path


async def app(scope: dict[str, Any], receive: Callable, send: Callable) -> None:
    """Vercel ASGI wrapper resolving x-forwarded-uri, __path and rewrite paths."""
    if scope.get("type") == "http":
        resolved_path = _resolve_request_path(scope)
        scope["path"] = resolved_path
        scope["raw_path"] = resolved_path.encode("latin1")

    await fastapi_app(scope, receive, send)


__all__ = ["app"]

