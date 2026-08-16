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
        min_size=settings.db_pool_min,
        max_size=settings.db_pool_max,
        open=True,
        connection_class=DictConnection,
        kwargs={"row_factory": dict_row},
        # --- F4-05: veritabanı yeniden başlarsa uygulama 500 dönmemeli ---
        #
        # Ölçülen arıza (13 Ağustos 2026): `pg_stat_statements` için
        # `pd-db` yeniden kuruldu; API ayaktaydı ve havuzdaki bağlantılar
        # koptu. Havuz onları KONTROL ETMEDEN dağıttı ve `/feed`
        # `psycopg.errors.AdminShutdown: terminating connection due to
        # administrator command` ile HTTP 500 verdi.
        #
        # `check` her ödünç vermeden önce bağlantıyı sınar; ölüyse havuz
        # onu atar ve yenisini kurar. Maliyeti istek başına bir
        # round-trip'tir — ölçüldü: feed p95 26 ms'den 33 ms'ye çıktı,
        # 800 ms hedefinin hâlâ 24 katı altında. Sessiz bir 500'ün
        # bedeli bundan yüksektir.
        check=ConnectionPool.check_connection,
        # Uzun ömürlü bağlantılar sunucu tarafı zaman aşımlarına ve
        # bellek şişmesine takılır; saatte bir tazelenir.
        max_lifetime=3600,
        # Havuz boşsa sonsuza dek beklemektense hata ver: asılı kalan bir
        # istek, hata veren bir istekten daha kötü teşhis edilir.
        timeout=10,
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
