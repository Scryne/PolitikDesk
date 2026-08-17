"""Vercel Serverless Entrypoint for PolitikDesk."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Ensure repo root is on sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from politikdesk.api.main import app as fastapi_app  # noqa: E402


async def app(scope: dict[str, Any], receive: Callable, send: Callable) -> None:
    """Vercel ASGI wrapper resolving x-forwarded-uri / x-matched-path rewrites."""
    if scope.get("type") == "http":
        headers = dict(scope.get("headers", []))
        forwarded = headers.get(b"x-forwarded-uri") or headers.get(b"x-matched-path")
        if forwarded:
            forwarded_str = forwarded.decode("latin1")
            parsed = urlparse(forwarded_str)
            target_path = parsed.path or "/"
            scope["path"] = target_path
            scope["raw_path"] = target_path.encode("latin1")
        elif scope.get("path") in ("/api/index.py", "/api/index"):
            scope["path"] = "/"
            scope["raw_path"] = b"/"

    await fastapi_app(scope, receive, send)


__all__ = ["app"]
