from __future__ import annotations

import os
from collections.abc import Generator

import pytest

from politikdesk.config import Settings

# Testler kendi ayarlarıyla koşsun; geliştiricinin .env'i sızmasın.
os.environ.setdefault("PD_ENV", "test")
os.environ.setdefault("PD_LOG_FORMAT", "console")

# ...ve `.env` DOSYASI da sızmasın.
Settings.model_config["env_file"] = None


def _get_test_dsn() -> str | None:
    """Test veritabanı DSN'ini belirler ve güvenlik kontrollerini uygular."""
    test_dsn = os.environ.get("PD_TEST_DATABASE_URL")
    prod_dsn = os.environ.get("PD_DATABASE_URL")

    # 1. PD_TEST_DATABASE_URL varsa öncelikli olarak kullanılır
    if test_dsn:
        # Uygulama kodlarının (politikdesk.db) da test veritabanına bağlanması için ortam değişkeni güncellenir
        os.environ["PD_DATABASE_URL"] = test_dsn
        return test_dsn

    # 2. Sadece PD_DATABASE_URL varsa güvenlik kontrolleri
    if prod_dsn:
        lower_dsn = prod_dsn.lower()
        if "prod" in lower_dsn or "production" in lower_dsn:
            pytest.fail(
                "GÜVENLİK İHLALİ: Test suite üretim veritabanına (production DSN) bağlanmaya çalıştı! "
                "Testlerin çalışması durduruldu."
            )
        return prod_dsn

    return None


@pytest.fixture(scope="session")
def db_conn():
    """Migration'ları uygulanmış bir veritabanına oturum düzeyinde bağlantı."""
    dsn = _get_test_dsn()
    if not dsn:
        if os.environ.get("PD_CI_REQUIRE_DB") == "1":
            pytest.fail(
                "PD_CI_REQUIRE_DB=1 fakat PD_DATABASE_URL/PD_TEST_DATABASE_URL ayarlı değil — DB testleri zorunludur (B-89)!"
            )
        pytest.skip("PD_DATABASE_URL ayarlı değil — veritabanı testleri atlandı.")

    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row

    try:
        conn = psycopg.connect(dsn, row_factory=dict_row)
    except Exception as exc:  # noqa: BLE001
        if os.environ.get("PD_CI_REQUIRE_DB") == "1":
            pytest.fail(f"PD_CI_REQUIRE_DB=1 fakat veritabanına bağlanılamadı: {exc}")
        pytest.skip(f"Veritabanına bağlanılamadı: {exc}")

    with conn:
        yield conn


@pytest.fixture(autouse=True)
def isolate_database_state() -> Generator[None, None, None]:
    """Her test öncesi ve sonrası tablo ID sınırlarını kaydeder ve test kirliliğini temizler."""
    dsn = _get_test_dsn()
    if not dsn:
        yield
        return

    psycopg = pytest.importorskip("psycopg")

    tables = [
        "event_feedback",
        "user_activity",
        "drafts",
        "briefings",
        "evidence",
        "claims",
        "scheduled_events",
        "articles",
        "events",
        "sources",
    ]

    max_ids: dict[str, int] = {}
    try:
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            for t in tables:
                try:
                    cur.execute(f"SELECT COALESCE(max(id), 0) FROM {t}")
                    res = cur.fetchone()
                    max_ids[t] = res[0] if res else 0
                except Exception:
                    pass
    except Exception:
        yield
        return

    yield

    # Test tamamlandıktan sonra testin eklediği satırları temizle
    try:
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            for t in tables:
                if t in max_ids:
                    cur.execute(f"DELETE FROM {t} WHERE id > %s", (max_ids[t],))
            # Test adları veya özel test slug'ları taşıyan artıkları da temizle
            cur.execute(
                "DELETE FROM event_feedback WHERE note LIKE 'Geri bildirim%' OR note LIKE 'Açılmamış%'"
            )
            cur.execute("DELETE FROM events WHERE title LIKE 'L6 Test%' OR title LIKE 'pytest%'")
            cur.execute("DELETE FROM sources WHERE slug LIKE 'pytest%'")
            conn.commit()
    except Exception:
        pass


def pytest_sessionfinish(session, exitstatus):  # noqa: ANN001
    """Veritabanı testleri atlandığında oturum sonunda görünür uyarı bandı basar (B-89)."""
    import sys

    if not _get_test_dsn() and os.environ.get("PD_CI_REQUIRE_DB") != "1":
        sys.stderr.write(
            "\n[UYARI] PD_DATABASE_URL tanimsiz — veritabani testleri ATLANDI (B-89).\n"
        )
