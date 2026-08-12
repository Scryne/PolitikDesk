"""Veritabanı bağlantı havuzu (psycopg 3)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from politikdesk.config import get_settings


@lru_cache(maxsize=1)
def get_pool() -> ConnectionPool:
    settings = get_settings()
    return ConnectionPool(
        conninfo=settings.database_url,
        min_size=1,
        max_size=10,
        open=True,
        kwargs={"row_factory": dict_row},
    )


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    """Havuzdan bir bağlantı ödünç alır."""
    with get_pool().connection() as conn:
        yield conn


def ping() -> bool:
    """Sağlık kontrolü için basit bir SELECT 1."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 AS ok")
        row = cur.fetchone()
        return bool(row and row["ok"] == 1)
