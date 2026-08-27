"""İmaj paketleme testleri (14 Ağustos 2026 arızası).

**Bu dosyanın var olma sebebi bir arızadır.**

F5-20, Resmî Gazete'nin TLS zincirindeki eksik ara sertifikayı
`certs/geotrust-tls-rsa-ca-g1.pem` ile kapatmıştı. Yerelde çalıştı,
testler yeşildi, `tests/test_resmi_gazete.py` demetin kurulduğunu
doğruluyordu. Ama `Dockerfile` `certs/` dizinini **kopyalamıyordu** ve
toplama işi konteynerde koşuyor.

Sonuç sessiz bir bozulmaydı: `ca_bundle_path()` dizin yoksa hata
vermez, yalnız certifi'ye düşer. Kaynak sağlık panosunda Resmî Gazete
24 saatte 1 kalemle amber kaldı, hata `CERTIFICATE_VERIFY_FAILED`
olarak göründü — sertifika sorunu sanıldı, oysa **paketleme** sorunuydu.

`scripts/check_deployment.py` çalışan konteynere bakar ama Docker
gerektirir; CI'ın `quality` işinde Docker yoktur. Buradaki testler
`Dockerfile`'ın kendisine bakar, yani kayma imaja hiç girmeden yakalanır.
"""

from __future__ import annotations

from pathlib import Path

from scripts.check_deployment import ASSET_DIRS, expected_assets

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO_ROOT / "Dockerfile"


def _copied_paths() -> set[str]:
    """Dockerfile'ın `COPY` ile imaja aldığı kaynak yolları."""
    copied: set[str] = set()
    for line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith("COPY "):
            continue
        # `COPY <kaynak>... <hedef>` — son alan hedeftir.
        parts = stripped.split()[1:]
        copied.update(part.rstrip("/") for part in parts[:-1])
    return copied


def test_runtime_asset_dirs_are_copied_into_the_image() -> None:
    """Kodun çalışma anında okuduğu her dizin imaja girmeli.

    Asıl arızanın testi budur: `certs/` `Dockerfile`'da yoktu.
    """
    copied = _copied_paths()
    missing = sorted(name for name in ASSET_DIRS if name not in copied)
    assert not missing, (
        f"Dockerfile bu dizin(ler)i imaja kopyalamiyor: {missing}. "
        "Kod bunlari calisma aninda okuyor; imajda yoksa konteynerde "
        "sessizce yanlis davranir. `COPY <dizin> ./<dizin>` eklenmeli."
    )


def test_asset_dirs_exist_in_repo_and_are_not_empty() -> None:
    """Denetimin kendisi boş kümeyle kandırılamamalı.

    `expected_assets()` boş liste dönerse `check_deployment` her şeyi
    "tamam" sayardı — dosya olmadığı için eksik de olmaz. Bu test
    denetleyicinin gerçekten bir şey beklediğini garanti eder.
    """
    for name, files in expected_assets().items():
        assert (REPO_ROOT / name).is_dir(), f"{name}/ dizini depoda yok"
        assert files, f"{name}/ bos — denetim anlamsizlasir"


def test_windows_batch_files_use_crlf() -> None:
    """`cmd.exe` `goto` etiketlerini BAYT OFSETİYLE arar.

    Dosya yalnız LF ile bittiğinde arama satır ortasına düşebiliyor ve
    komut satırın yarısını çalıştırıyor. Ölçülen belirti (14 Ağustos
    2026): `pd.cmd` LF iken `pd arch` / `pd lint` / `pd status` şunu
    veriyordu — yolun ilk harfi yutulmuştu:

        'olitikDesk' is not recognized as an internal or external command

    ⚠️ Arıza SABİT DEĞİLDİ: hangi komutun bozulacağı bayt kaymasına
    bağlıydı, yani bir satır eklemek bambaşka bir komutu bozabiliyordu.
    `.gitattributes` bunu `eol=crlf` ile sabitler; bu test de tutar.
    """
    for path in sorted(REPO_ROOT.glob("*.cmd")):
        data = path.read_bytes()
        lone_lf = data.replace(b"\r\n", b"").count(b"\n")
        assert lone_lf == 0, (
            f"{path.name}: {lone_lf} satir yalniz LF ile bitiyor. "
            "Toplu is dosyalari CRLF olmali (.gitattributes eol=crlf)."
        )


def test_gitattributes_pins_batch_line_endings() -> None:
    """Kural depoda sabitlenmeli; yoksa bir sonraki checkout geri alır."""
    attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.cmd" in attributes
    assert "eol=crlf" in attributes


def test_certs_dir_read_by_code_is_the_one_that_is_copied() -> None:
    """`http.py`'nin okuduğu dizin ile imaja kopyalanan aynı olmalı.

    `CERTS_DIR` yeniden adlandırılır ama `Dockerfile`/`ASSET_DIRS`
    güncellenmezse arıza birebir tekrarlar.
    """
    from politikdesk.ingestion.http import CERTS_DIR

    assert CERTS_DIR.name in ASSET_DIRS
    assert CERTS_DIR.resolve() == (REPO_ROOT / CERTS_DIR.name).resolve()


def test_sources_legislation_yml_is_in_asset_manifest() -> None:
    """`config/sources_legislation.yml` varlık manifestinde bulunmalı ve geçerli olmalı (F2)."""
    assets = expected_assets()
    assert "sources_legislation.yml" in assets.get("config", []), (
        "config/sources_legislation.yml beklenen asset listesinde bulunamadı."
    )
    leg_path = REPO_ROOT / "config" / "sources_legislation.yml"
    assert leg_path.is_file(), "config/sources_legislation.yml dosyası mevcut değil."
    import yaml

    data = yaml.safe_load(leg_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "sources" in data
    assert len(data["sources"]) > 0


def test_all_required_runtime_packages_exist() -> None:
    """verticals, political_memory ve web.ui paketleri repo içinde mevcut ve import edilebilir (F2)."""
    required_pkgs = [
        "politikdesk.verticals",
        "politikdesk.political_memory",
        "politikdesk.web.ui",
    ]
    for pkg in required_pkgs:
        mod = __import__(pkg, fromlist=["*"])
        assert mod is not None, f"{pkg} modülü import edilemedi."


def test_all_required_adapters_are_registered() -> None:
    """Gerekli tüm adaptörler ADAPTERS sözlüğünde kayıtlı olmalı ve fetch metodu içermeli (F2)."""
    from politikdesk.ingestion.pipeline import ADAPTERS

    required = ["cumhurbaskanligi", "tbmm", "sayistay", "resmi_gazete", "tuik_sdmx", "rss"]
    for adapter_name in required:
        assert adapter_name in ADAPTERS, f"Adaptör kayıtlı değil: {adapter_name}"
        adapter_cls = ADAPTERS[adapter_name]
        assert hasattr(adapter_cls, "fetch"), f"{adapter_name} sınıfında 'fetch' metodu yok."
        assert callable(adapter_cls.fetch), f"{adapter_name}.fetch çağrılabilir değil."


def test_dockerignore_preserves_runtime_roots() -> None:
    """.dockerignore dosyasının kritik çalışma zamanı dizinlerini dışlamadığını doğrular (F2)."""
    dockerignore_path = REPO_ROOT / ".dockerignore"
    assert dockerignore_path.is_file(), ".dockerignore dosyası bulunamadı."
    lines = [
        line.strip()
        for line in dockerignore_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    forbidden_ignores = ["politikdesk", "config", "certs", "migrations", "scripts"]
    for line in lines:
        for root in forbidden_ignores:
            assert line != root and line != f"{root}/" and line != f"/{root}", (
                f".dockerignore çalışma zamanı kök dizini '{root}'u dışlıyor: '{line}'"
            )


def test_makefile_and_pd_cmd_commands_are_synced() -> None:
    """Makefile ve pd.cmd arasındaki temel iş akışı komutlarının senkronizasyonunu denetler."""
    import re

    makefile_path = REPO_ROOT / "Makefile"
    pd_cmd_path = REPO_ROOT / "pd.cmd"

    assert makefile_path.is_file(), "Makefile bulunamadı."
    assert pd_cmd_path.is_file(), "pd.cmd bulunamadı."

    # Makefile .PHONY hedefleri
    phony_match = re.search(
        r"^\.PHONY:\s*(.+)$", makefile_path.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert phony_match, "Makefile içinde .PHONY satırı bulunamadı."
    make_targets = set(phony_match.group(1).split())

    # pd.cmd :cmd_ etiketleri
    pd_cmd_text = pd_cmd_path.read_text(encoding="utf-8")
    pd_commands = set(re.findall(r"^:cmd_([a-zA-Z0-9_\-]+)", pd_cmd_text, re.MULTILINE))

    # Ortak zorunlu temel komutlar listesi
    core_commands = {
        "start",
        "stop",
        "restart",
        "update",
        "migrate",
        "test",
        "lint",
        "audit",
        "ci",
        "sync",
        "ingest",
        "embed",
        "entities",
        "cluster",
        "claims",
        "evidence",
        "context",
        "briefing",
        "metrics",
        "health",
        "pipeline-health",
        "watchdog",
        "backup",
        "backup-list",
        "backup-verify",
        "backup-restore",
        "deploy-check",
    }

    missing_in_make = core_commands - make_targets
    missing_in_pd = core_commands - pd_commands

    assert not missing_in_make, f"Makefile içinde eksik temel komut(lar): {missing_in_make}"
    assert not missing_in_pd, f"pd.cmd içinde eksik temel komut(lar): {missing_in_pd}"


# ══════════════════════════════════════ test ortamının belirliliği (18 Ağu 2026)
def test_database_tests_are_not_silently_skipped_when_env_defines_a_dsn() -> None:
    """DB testlerinin koşup koşmaması TEST SIRASINA bağlı olmamalı.

    **Bu testin var olma sebebi bir denetim bulgusudur.**

    `conftest.py` `Settings.model_config["env_file"] = None` yazarak
    `.env`'in sızmasını engellediğini sanıyordu. Engellemiyordu:
    `config.get_settings()` her çağrısında `load_env_file()` koşar ve
    `.env`'deki her anahtarı doğrudan `os.environ`'a kopyalar. Yani `.env`
    yine yükleniyordu — ama NE ZAMAN yükleneceği, ilk `get_settings()`
    çağrısını hangi testin tetiklediğine bağlıydı.

    Ölçülen sonuç:

        pytest                      -> 65 veritabani testi kosar
        pytest tests/test_schema.py -> ayni testlerin 9'u SESSIZCE atlanir

    Atlananlar arasında pazarlıksız kısıtları koruyanlar vardı (alıntı
    300 karakter sınırı, tam metin saklama yasağı). Koşmayan bir kısıt
    testi kısıtı korumaz; üstelik `pd ci` her iki durumda da yeşil der.

    Çözüm `conftest`'te `.env`'i açıkça ve tek seferde yüklemekti. Bu
    test o çözümü yerinde tutar: `.env` bir DSN tanımlıyorsa, testler
    hangi sırayla koşarsa koşsun onu görmelidir.
    """
    import os

    from politikdesk.config import resolve_env_file_path

    env_path = resolve_env_file_path()
    if not env_path or not env_path.is_file():
        return  # `.env` yok — CI konteyneri gibi; söylenecek bir şey de yok.

    from dotenv import dotenv_values

    declared = dotenv_values(env_path, encoding="utf-8")
    if not declared.get("PD_DATABASE_URL"):
        return

    assert os.environ.get("PD_DATABASE_URL"), (
        "`.env` bir PD_DATABASE_URL tanimliyor ama surecin ortaminda yok. "
        "conftest.py `.env`'i acikca yuklemeli; aksi halde veritabani "
        "testleri test sirasina gore SESSIZCE atlanir."
    )
