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

# Postgres ayarlı ama kapalıysa (yerelde `docker compose up -d db` unutulmuş), web katmanından
# veritabanına dokunan her istek havuzda 10 sn bekliyordu: tam koşu saatler sürüyor, pytest-timeout
# ortada kesiyordu (2026-10-26 denetimi, `test_csp_nonce_rotation_and_entropy`). Erişilemeyen
# veritabanı artık "veritabanı yok" sayılır: uygulama bağlantıda havuzu beklemeden hata verir, `db`
# işaretli ve `db_conn` kullanan testler atlanır, oturum sonunda uyarı bandı basılır. Ortam
# değişkenlerine dokunulmaz (`.env` yükleme testleri onları okur). CI bu gevşetmeyi yapmaz
# (`PD_CI_REQUIRE_DB=1`): orada veritabanı yoksa testler düşmeli (B-89).


def _veritabani_erisimini_dene() -> str | None:
    """Etkin DSN'e 2 sn içinde bağlanılamıyorsa nedenini döner; bağlanılıyorsa ya da denenmemeliyse None."""
    if os.environ.get("PD_CI_REQUIRE_DB") == "1":
        return None
    dsn = (
        os.environ.get("PD_TEST_DATABASE_URL")
        or os.environ.get("PD_DATABASE_URL")
        or Settings.model_fields["database_url"].default
    )
    if not dsn or any(k in dsn.lower() for k in ("prod", "production", "live", "primary")):
        return None  # üretim DSN'i denenmez; `_get_test_dsn` fail-closed ile durdurur
    try:
        import psycopg

        with psycopg.connect(dsn, connect_timeout=2):
            return None
    except Exception as exc:  # noqa: BLE001 — her bağlantı hatası "erişilemiyor" demektir
        return (
            f"{type(exc).__name__}: {str(exc).strip().splitlines()[0] if str(exc).strip() else '-'}"
        )


def _veritabani_yapilandirilmamis() -> bool:
    return False


_VERITABANI_ERISILEMEDI = _veritabani_erisimini_dene()
if _VERITABANI_ERISILEMEDI:
    import politikdesk.db as _pd_db

    # `db.connection()` bu kontrolü modül üzerinden çağırır: havuz hiç açılmaz, hata anında gelir.
    _pd_db.is_db_configured = _veritabani_yapilandirilmamis

# Test ortamında varsayılan olarak API kimlik doğrulaması kapalıdır (boş);
# ilgili güvenlik testleri monkeypatch ile token enjekte eder.
os.environ["PD_API_TOKEN"] = ""
from politikdesk.config import get_settings  # noqa: E402

get_settings.cache_clear()


def _get_test_dsn() -> str | None:
    """Test veritabanı DSN'ini belirler ve katı fail-closed güvenlik kontrollerini uygular.

    Invariant: TEST DATABASE != PRODUCTION DATABASE (Spec §11.1).
    Testler hiçbir koşulda üretim veya canlı veritabanına bağlanamaz.
    """
    env = (os.environ.get("PD_ENV") or "").lower().strip()
    if env in {"production", "prod", "prd", "live"}:
        pytest.fail(
            f"KRİTİK GÜVENLİK İHLALİ: PD_ENV='{env}' iken test paketi çalıştırılamaz! "
            "Üretim ortamı test izolasyonu kuralı ihlal edildi (Fail-Closed)."
        )

    test_dsn = os.environ.get("PD_TEST_DATABASE_URL")
    prod_dsn = os.environ.get("PD_DATABASE_URL")
    forbidden_keywords = ("prod", "production", "live", "primary")

    # 1. PD_TEST_DATABASE_URL varsa öncelikli olarak kullanılır
    if test_dsn:
        lower_test = test_dsn.lower()
        if any(k in lower_test for k in forbidden_keywords):
            pytest.fail(
                "KRİTİK GÜVENLİK İHLALİ: PD_TEST_DATABASE_URL bir üretim/canlı veritabanına işaret ediyor! "
                "Testlerin çalışması derhal durduruldu."
            )
        # Uygulama kodlarının (politikdesk.db) da test veritabanına bağlanması için ortam değişkeni güncellenir
        os.environ["PD_DATABASE_URL"] = test_dsn
        return test_dsn

    # 2. PD_TEST_DATABASE_URL yoksa ve PD_DATABASE_URL mevcutsa
    if prod_dsn:
        lower_dsn = prod_dsn.lower()
        if any(k in lower_dsn for k in forbidden_keywords):
            pytest.fail(
                "KRİTİK GÜVENLİK İHLALİ: Test suite üretim/canlı veritabanına (production DSN) bağlanmaya çalıştı! "
                "Testlerin çalışması durduruldu."
            )
        return prod_dsn

    return None


@pytest.fixture(scope="session", autouse=True)
def _baseline_sources() -> None:
    """Kaynak tablosu boşsa `config/sources*.yml`'den bir kez senkronlar (`pd seed` eşdeğeri).

    Olay/makale tohumlayan testler "en az iki aktif kaynak" varsayar. Bu varsayım yalnız
    geliştiricinin dolu veritabanında tutuyordu; CI'ın taze veritabanında (yalnız migration)
    `IndexError` ile düşüyordu. Kaynaklar üretim verisi değil yapılandırmadır: tohumlamak
    testi hermetik yapar, canlı veriye bağımlılık eklemez.
    """
    dsn = _get_test_dsn()
    if not dsn or _VERITABANI_ERISILEMEDI:
        return
    try:
        import psycopg

        with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM sources")
            row = cur.fetchone()
            if row is not None and int(row[0]) > 0:
                return
    except Exception:  # noqa: BLE001 — DB yoksa DB testleri zaten kendi atlanır
        return

    from politikdesk.ingestion.sources import load_all_configs, sync_to_database

    sync_to_database(load_all_configs())


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


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Veritabanına erişilemeyen oturumda `db` işaretli ya da `db_conn` isteyen testler koşmaz, atlanır."""
    needs_db = item.get_closest_marker("db") or "db_conn" in getattr(item, "fixturenames", ())
    if _VERITABANI_ERISILEMEDI and needs_db:
        pytest.skip(
            f"Veritabanına erişilemedi, veritabanı testi atlandı ({_VERITABANI_ERISILEMEDI})."
        )


def pytest_sessionfinish(session, exitstatus):  # noqa: ANN001
    """Veritabanı testleri atlandığında oturum sonunda görünür uyarı bandı basar (B-89)."""
    import sys

    if _VERITABANI_ERISILEMEDI:
        sys.stderr.write(
            "\n[UYARI] Veritabanina erisilemedi — veritabani testleri ATLANDI "
            "(Postgres kapali mi? `docker compose up -d db`).\n"
        )
    elif not _get_test_dsn() and os.environ.get("PD_CI_REQUIRE_DB") != "1":
        sys.stderr.write(
            "\n[UYARI] PD_DATABASE_URL tanimsiz — veritabani testleri ATLANDI (B-89).\n"
        )
