"""Veritabanı bağlantı havuzu (psycopg 3)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

import psycopg
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from politikdesk.config import get_settings

# Havuz `dict_row` ile açılır; tip parametresi bunu tip denetleyicisine de
# söyler. Aksi halde mypy her `cur.fetchone()` sonucunu tuple sanar ve
# `row["id"]` erişimlerini hata olarak işaretler (B-40).
DictConnection = psycopg.Connection[DictRow]


@lru_cache(maxsize=1)
def get_pool() -> ConnectionPool[DictConnection]:
    settings = get_settings()
    return ConnectionPool(
        conninfo=settings.database_url,
        min_size=min(settings.db_pool_min, 1),
        max_size=settings.db_pool_max,
        open=False,
        connection_class=DictConnection,
        kwargs={"row_factory": dict_row},
        check=ConnectionPool.check_connection,
        max_lifetime=3600,
        timeout=5,
    )


@contextmanager
def connection() -> Iterator[DictConnection]:
    """Havuzdan bir bağlantı ödünç alır."""
    with get_pool().connection() as conn:
        yield conn


def fetch_one(cur: psycopg.Cursor[DictRow]) -> DictRow:
    """`RETURNING` veya toplama (aggregate) sorgusunun tek satırını döndürür.

    Bu sorgularda satır garantidir; yine de `fetchone()` imzası `None`
    içerir. Doğrudan indekslemek, beklenmedik durumda anlamsız bir
    `TypeError: 'NoneType' object is not subscriptable` üretiyordu (B-40).
    """
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(
            "Satır dönmesi beklenen sorgu boş döndü — sorgu ya da şema değişmiş olabilir."
        )
    return row


def ping() -> bool:
    """Sağlık kontrolü için basit bir SELECT 1."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 AS ok")
        row = cur.fetchone()
        return bool(row and row["ok"] == 1)
