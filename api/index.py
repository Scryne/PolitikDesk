"""Vercel Serverless Entrypoint for PolitikDesk."""

from __future__ import annotations

from typing import Any

from politikdesk.api.main import app as _fastapi_app


async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    """ASGI wrapper to resolve Vercel rewrite paths correctly."""
    if scope["type"] == "http":
        path = scope.get("path", "")
        # Vercel rewrites send /api/index.py or /api/index as scope['path']
        if path in ("/api/index.py", "/api/index", "/api/index/", "/api", "/api/"):
            headers = dict(scope.get("headers", []))
            forwarded_uri = headers.get(b"x-forwarded-uri", b"").decode("latin-1")
            matched_path = headers.get(b"x-matched-path", b"").decode("latin-1")
            now_route = headers.get(b"x-now-route-matches", b"").decode("latin-1")

            orig = ""
            if forwarded_uri:
                orig = forwarded_uri.split("?")[0]
            elif matched_path and not matched_path.startswith("/api/index"):
                orig = matched_path
            elif now_route and "1=" in now_route:
                # e.g. 1=%2Ffeed -> /feed
                import urllib.parse
                parts = dict(urllib.parse.parse_qsl(now_route))
                if "1" in parts:
                    orig = parts["1"]

            scope["path"] = orig or "/"
        elif path.startswith("/api/index.py/"):
            scope["path"] = path[len("/api/index.py") :]
        elif path.startswith("/api/index/"):
            scope["path"] = path[len("/api/index") :]

    await _fastapi_app(scope, receive, send)


__all__ = ["app"]

