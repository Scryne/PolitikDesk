"""Vercel Serverless Entrypoint for PolitikDesk."""

from politikdesk.api.main import app

# Vercel serverless runtime exposes `app`
__all__ = ["app"]
