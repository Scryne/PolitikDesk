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
