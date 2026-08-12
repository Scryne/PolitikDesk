from __future__ import annotations

import os

import pytest

# Testler kendi ayarlarıyla koşsun; geliştiricinin .env'i sızmasın.
os.environ.setdefault("PD_ENV", "test")
os.environ.setdefault("PD_LOG_FORMAT", "console")


def _database_url() -> str | None:
    return os.environ.get("PD_DATABASE_URL")


@pytest.fixture(scope="session")
def db_conn():
    """Migration'ları uygulanmış bir veritabanına bağlantı.

    PD_DATABASE_URL yoksa DB testleri atlanır (yerelde Docker olmadan da
    test paketi koşabilsin). CI'da postgres servisi ayakta olduğu için
    bu testler her zaman çalışır.
    """
    dsn = _database_url()
    if not dsn:
        pytest.skip("PD_DATABASE_URL ayarlı değil — veritabanı testleri atlandı.")

    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row

    try:
        conn = psycopg.connect(dsn, row_factory=dict_row)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Veritabanına bağlanılamadı: {exc}")

    with conn:
        yield conn
