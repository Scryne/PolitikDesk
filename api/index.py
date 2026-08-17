"""Vercel Serverless Entrypoint for PolitikDesk."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is on sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from politikdesk.api.main import app  # noqa: E402

__all__ = ["app"]
