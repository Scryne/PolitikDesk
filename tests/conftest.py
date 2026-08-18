from __future__ import annotations

import os
from collections.abc import Generator

import pytest

from politikdesk.config import Settings

# Testler kendi ayarlarıyla koşsun.
os.environ.setdefault("PD_ENV", "test")
os.environ.setdefault("PD_LOG_FORMAT", "console")

# Pydantic'in kendi `.env` okuyucusu kapatılır.
Settings.model_config["env_file"] = None

# ...ama bu TEK BAŞINA yetmez ve yıllarca yettiği sanıldı.
#
# `config.get_settings()` her çağrısında `load_env_file()` koşar ve `.env`
# içindeki HER anahtarı doğrudan `os.environ`'a kopyalar. Yani pydantic
# ayarı devre dışı bırakılsa bile `.env` sürecin ortamına giriyordu —
# yalnızca NE ZAMAN gireceği belirsizdi: ilk `get_settings()` çağrısını
# hangi testin tetiklediğine, yani TEST SIRASINA bağlıydı.
#
# Somut sonucu (18 Ağustos 2026 denetimi):
#
#     pytest                      -> 65 veritabanı testi KOŞAR
#     pytest tests/test_schema.py -> aynı testlerin 9'u SESSİZCE ATLANIR
#
# Atlananların arasında pazarlıksız kısıtları koruyanlar vardı: alıntı
# 300 karakter sınırı, tam metin saklama yasağı. Bir kısıt testi
# "yeşil" derken hiç koşmamışsa, kısıt korunmuyor demektir.
#
# Çözüm: belirsizliği kaldır. `.env` BURADA, açıkça ve tek seferde
# yüklenir; hangi testin neyi import ettiği artık sonucu değiştirmez.
# Kabuktan verilen değer yine `.env`'i yener (`load_env_file` mevcut
# değişkenleri ezmez).
from politikdesk.config import load_env_file  # noqa: E402

load_env_file()


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


@pytest.fixture
def db_conn():
    """Migration'ları uygulanmış bir veritabanına bağlantı."""
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
        conn = psycopg.connect(dsn, row_factory=dict_row, autocommit=True)
    except Exception as exc:  # noqa: BLE001
        if os.environ.get("PD_CI_REQUIRE_DB") == "1":
            pytest.fail(f"PD_CI_REQUIRE_DB=1 fakat veritabanına bağlanılamadı: {exc}")
        pytest.skip(f"Veritabanına bağlanılamadı: {exc}")

    try:
        yield conn
    finally:
        import contextlib

        with contextlib.suppress(Exception):
            conn.close()


@pytest.fixture(autouse=True)
def isolate_database_state(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Her test öncesi ve sonrası tablo ID sınırlarını kaydeder ve test kirliliğini temizler."""
    if not request.node.get_closest_marker("db") and "db_conn" not in request.fixturenames:
        yield
        return

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
            # `test-` öneki de süpürülür: `db_conn` autocommit ile bağlanır,
            # dolayısıyla testlerdeki `rollback()` çağrıları bu satırları
            # geri almaz ve id-su-seviyesi süpürgesi bir kez kaçırırsa
            # satır KALICI olur. 18 Ağustos 2026'da `test-excerpt-src` böyle
            # kaçmış, canlı veritabanında AKTİF bir Tier-1 kaynak olarak
            # kalmış ve toplayıcı onu 5 dakikada bir çekmeye çalışıyordu.
            cur.execute("DELETE FROM sources WHERE slug LIKE 'pytest%' OR slug LIKE 'test-%'")
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
