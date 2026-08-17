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

from politikdesk.api.main import app as fastapi_app  # noqa: E402


async def app(scope: dict[str, Any], receive: Callable, send: Callable) -> None:
    """Vercel ASGI wrapper resolving x-forwarded-uri, __path and rewrite paths."""
    if scope.get("type") == "http":
        headers = dict(scope.get("headers", []))
        resolved_path: str | None = None

        # 1. Check x-forwarded-uri (e.g. proxy or test suite)
        if b"x-forwarded-uri" in headers:
            forwarded_str = headers[b"x-forwarded-uri"].decode("latin1")
            resolved_path = urlparse(forwarded_str).path or "/"

        # 2. Check __path query parameter injected by vercel.json rewrite
        raw_qs = scope.get("query_string", b"").decode("latin1")
        if raw_qs:
            qs_dict = parse_qs(raw_qs, keep_blank_values=True)
            if "__path" in qs_dict and not resolved_path:
                injected = qs_dict.pop("__path")[0]
                resolved_path = ("/" + injected.lstrip("/")) if injected else "/"
                # Clean up query string so __path is not leaked to route handlers
                new_qs = urlencode([(k, v) for k, vs in qs_dict.items() for v in vs])
                scope["query_string"] = new_qs.encode("latin1")

        # 3. Check scope["path"] directly
        if not resolved_path:
            current_path = scope.get("path", "/")
            if current_path in ("/api/index.py", "/api/index", "/api", ""):
                resolved_path = "/"
            elif current_path.startswith("/api/index.py/"):
                resolved_path = current_path[len("/api/index.py") :] or "/"
            else:
                resolved_path = current_path

        scope["path"] = resolved_path
        scope["raw_path"] = resolved_path.encode("latin1")

    await fastapi_app(scope, receive, send)


__all__ = ["app"]
