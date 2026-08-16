"""Tasarım sistemi testleri (DESIGN.md Bölüm 5, 6, 12, 13, 15).

**Bu dosyanın var olma sebebi bir gözlemdir:** tasarım kuralları belge
olarak yazıldığında ilk sprintte tutulur, üçüncüde unutulur. Bu depoda her
pazarlıksız kısıt bir testle korunuyor; arayüz kuralları da öyle olmalı.

Korunan altı şey:

  1. `tokens.py` dışında ham hex yok — token sistemi sızdırmıyor.
  2. Palet WCAG'ı geçiyor — açık VE koyu temada, her metin/zemin çifti.
  3. Fontlarda Türkçe glif tam — `İ ı Ğ ğ Ş ş Ç ç Ö ö Ü ü`.
  4. Font dosyaları gerçekten var — CSS'in gösterdiği yol boş değil.
  5. `text-transform: uppercase` yok — Türkçede `i → I` bozar (Ek B.3).
  6. Emoji ikon yok — tek ikon seti (Bölüm 13.4).

`DESIGN.md` Bölüm 15'in "Token & tutarlılık" ve "Erişilebilirlik"
maddeleri buradan otomatik doğrulanır; DoD'nin o kısmı göz denetimi
olmaktan çıkar.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from politikdesk.web.ui import icons
from politikdesk.web.ui.css import stylesheet
from politikdesk.web.ui.tokens import DARK, LIGHT, contrast_ratio

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = REPO_ROOT / "politikdesk"
TOKENS_FILE = PACKAGE_DIR / "web" / "ui" / "tokens.py"
FONT_DIR = PACKAGE_DIR / "web" / "static" / "fonts"

# E-posta gövdesi token sisteminin DIŞINDADIR ve bu bilinçlidir: e-posta
# istemcileri CSS değişkenini (`var(--color-fg)`) desteklemez — Gmail
# `<style>` bloğunu da çoğu zaman soyar. Tek yol satır içi ham hex.
#
# Sızıntı olmaması için renkler `tokens.LIGHT`'tan OKUNUR, elle yazılmaz;
# `test_email_palette_comes_from_tokens` bunu doğrular. Yani kural
# gevşetilmiyor, farklı bir mekanizmayla korunuyor.
EMAIL_RENDERER = PACKAGE_DIR / "briefing" / "renderer.py"

HEX_EXEMPT = {TOKENS_FILE, EMAIL_RENDERER}
HEX_PATTERN = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def _python_sources() -> list[Path]:
    return [path for path in PACKAGE_DIR.rglob("*.py") if "__pycache__" not in path.parts]


def _emittable_strings(path: Path) -> list[str]:
    """Dosyadaki, ÇIKTIYA ULAŞABİLECEK dize sabitleri.

    Yorumlar ve docstring'ler dışlanır — gerekçesi
    `tests/test_web.py::_emittable_strings` ile aynı ve bu depoda
    yerleşiktir: burada kısıtlar koda yazılıyor, dolayısıyla bir
    docstring yasağı AÇIKLAYABİLİR. Ham metin taraması o açıklamayı
    ihlal sanardı — test, kendisini var eden disiplini cezalandırırdı.

    Somut örnek: `ui/icons.py`'nin başlığı "emoji ikon olarak
    kullanılmaz" derken 🟢 yazıyor. Yasağı anlatan cümle, yasağın
    ihlali değildir.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            first = next(iter(getattr(node, "body", [])), None)
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                docstrings.add(id(first.value))

    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


# ═══════════════════════════════════════════ 1. ham hex sızıntısı
def test_raw_hex_appears_only_in_the_token_file() -> None:
    """DESIGN.md Bölüm 5.1: hiçbir bileşende ham hex yok, sadece token.

    `#FFF` gibi 3 haneli biçim de aranmalı mı? Hayır — 6 haneli kalıp
    pratikte yeterli ve 3 hane, `#{id}` gibi f-string parçalarıyla
    karışıyor. Kaçan bir `#FFF` görsel denetimde zaten yakalanır;
    kaçan bir `#0969da` yakalanmaz.
    """
    offenders: list[str] = []
    for path in _python_sources():
        if path in HEX_EXEMPT:
            continue
        relative = path.relative_to(REPO_ROOT).as_posix()
        offenders += [
            f"{relative}: {value[:70]}"
            for value in _emittable_strings(path)
            if HEX_PATTERN.search(value)
        ]

    assert not offenders, (
        "Token sistemi sizdiriyor — ham hex bulundu:\n  "
        + "\n  ".join(offenders)
        + "\n\nDESIGN.md Bolum 5.1: renk yalnizca web/ui/tokens.py'de tanimlanir."
    )


def test_email_palette_comes_from_tokens() -> None:
    """E-posta gövdesi muaf ama BAŞIBOŞ değil.

    `renderer.py` satır içi hex kullanmak zorunda (e-posta istemcileri CSS
    değişkeni desteklemez) — ama o hex'leri `tokens.LIGHT`'tan okumalı.
    Aksi halde uygulamanın paleti değişince e-posta eski renklerde kalır
    ve iki farklı ürün gibi görünür.
    """
    source = EMAIL_RENDERER.read_text(encoding="utf-8")
    assert "from politikdesk.web.ui.tokens import" in source, (
        "briefing/renderer.py rengi tokens.py'den okumali; ham hex yazmamali."
    )
    literals = [
        value
        for value in _emittable_strings(EMAIL_RENDERER)
        if HEX_PATTERN.fullmatch(value.strip())
    ]
    assert not literals, f"E-posta sablonunda elle yazilmis renk: {literals}. tokens.LIGHT'tan oku."


def test_the_token_file_actually_contains_colours() -> None:
    """Denetim boş kümeyle kandırılamamalı.

    Yukarıdaki test, `tokens.py` boşalırsa da geçerdi. Bu test onun
    dayanağını doğrular: renkler gerçekten orada.
    """
    assert HEX_PATTERN.search(TOKENS_FILE.read_text(encoding="utf-8"))
    assert len(LIGHT) >= 20
    assert set(LIGHT) == set(DARK), (
        "Koyu tema aynı token adlarını taşımalı (DESIGN.md 5.2); eksik/fazla: "
        f"{set(LIGHT) ^ set(DARK)}"
    )


# ═══════════════════════════════════════════ 2. WCAG kontrastı
# (ön plan, zemin) — metin çiftleri 4.5:1, UI çiftleri 3:1 ister.
TEXT_PAIRS = (
    ("color-fg", "color-bg"),
    ("color-fg", "color-surface"),
    ("color-fg", "color-surface-sunken"),
    ("color-fg-muted", "color-bg"),
    ("color-fg-muted", "color-surface"),
    ("color-fg-subtle", "color-bg"),
    ("color-fg-subtle", "color-surface"),
    ("color-fg-subtle", "color-surface-sunken"),
    ("color-accent", "color-bg"),
    ("color-accent", "color-surface"),
    ("color-accent", "color-accent-subtle"),
    ("color-fg-on-accent", "color-accent"),
    # Kanıt skalası: rozet zemini üzerinde VE kart üzerinde okunmalı.
    ("color-strong", "color-strong-subtle"),
    ("color-partial", "color-partial-subtle"),
    ("color-single", "color-single-subtle"),
    ("color-contra", "color-contra-subtle"),
    ("color-unverified", "color-unverified-subtle"),
    ("color-strong", "color-surface"),
    ("color-partial", "color-surface"),
    ("color-single", "color-surface"),
    ("color-contra", "color-surface"),
)

UI_PAIRS = (
    # Etkileşimli kenarlık (input, checkbox) — WCAG 1.4.11.
    ("color-border-strong", "color-surface"),
    ("color-border-strong", "color-bg"),
    *((f"color-chart-{index}", "color-surface") for index in range(1, 7)),
)


@pytest.mark.parametrize("theme_name", ["light", "dark"])
@pytest.mark.parametrize("foreground,background", TEXT_PAIRS)
def test_text_contrast_meets_wcag_aa(theme_name: str, foreground: str, background: str) -> None:
    palette = LIGHT if theme_name == "light" else DARK
    ratio = contrast_ratio(palette[foreground], palette[background])
    assert ratio >= 4.5, (
        f"{theme_name}: {foreground} ({palette[foreground]}) uzerinde "
        f"{background} ({palette[background]}) = {ratio:.2f}:1, "
        f"gereken 4.5:1 (DESIGN.md Bolum 12)."
    )


@pytest.mark.parametrize("theme_name", ["light", "dark"])
@pytest.mark.parametrize("foreground,background", UI_PAIRS)
def test_ui_contrast_meets_wcag_aa(theme_name: str, foreground: str, background: str) -> None:
    palette = LIGHT if theme_name == "light" else DARK
    ratio = contrast_ratio(palette[foreground], palette[background])
    assert ratio >= 3.0, (
        f"{theme_name}: {foreground} ({palette[foreground]}) uzerinde "
        f"{background} ({palette[background]}) = {ratio:.2f}:1, "
        f"UI bileseni icin gereken 3:1 (WCAG 1.4.11)."
    )


def test_dark_theme_avoids_pure_black() -> None:
    """DESIGN.md 5.2: saf siyah yasak — göz yorar, gölge görünmez."""
    assert DARK["color-bg"].upper() != "#000000"
    assert DARK["color-surface"].upper() != "#000000"


# ═══════════════════════════════════════════ 3-4. font ve Türkçe glif
TURKISH_CODEPOINTS = {
    0x0130: "I (noktali buyuk)",
    0x0131: "i (noktasiz kucuk)",
    0x011E: "G breve",
    0x011F: "g breve",
    0x015E: "S cedilla",
    0x015F: "s cedilla",
    0x00C7: "C cedilla",
    0x00E7: "c cedilla",
    0x00D6: "O umlaut",
    0x00F6: "o umlaut",
    0x00DC: "U umlaut",
    0x00FC: "u umlaut",
}

FONT_FAMILIES = ("inter-tight", "ibm-plex-mono", "instrument-serif")


@pytest.mark.parametrize("family", FONT_FAMILIES)
def test_font_files_exist(family: str) -> None:
    """CSS'in gösterdiği dosya gerçekten var mı?

    Yoksa tarayıcı sessizce fallback fonta düşer ve arayüzde iki font
    karışır — DESIGN.md 6.1'in "tasarımı anında ucuzlatır" dediği durum.
    Sessiz olduğu için görsel denetimde de kolayca kaçar.
    """
    for subset in ("latin", "latin-ext"):
        path = FONT_DIR / f"{family}-{subset}.woff2"
        assert path.is_file(), f"Font dosyasi yok: {path}"
        assert path.stat().st_size > 2000, f"Font dosyasi bozuk/bos: {path}"


@pytest.mark.parametrize("family", FONT_FAMILIES)
def test_fonts_cover_turkish_glyphs(family: str) -> None:
    """DESIGN.md Bölüm 6.1 — atlanamaz kontrol.

    `latin` ve `latin-ext` alt kümelerinin BİRLEŞİMİNE bakılır: Google'ın
    `latin` alt kümesi Ç Ö Ü gibi Latin-1 karakterlerini taşır, `latin-ext`
    ise Ğ Ş İ'yi. Tek dosyaya bakan bir test yanlış alarm verirdi.
    """
    fonttools = pytest.importorskip(
        "fontTools.ttLib",
        reason="fonttools kurulu degil — glif denetimi atlandi",
    )
    pytest.importorskip("brotli", reason="brotli kurulu degil (woff2 acilamaz)")

    covered: set[int] = set()
    for subset in ("latin", "latin-ext"):
        font = fonttools.TTFont(FONT_DIR / f"{family}-{subset}.woff2")
        covered |= set(font.getBestCmap())

    missing = [name for code, name in TURKISH_CODEPOINTS.items() if code not in covered]
    assert not missing, (
        f"{family} fontunda Turkce glif eksik: {missing}. "
        "Eksik glif tarayicida fallback tetikler ve arayuzde iki font karisir."
    )


def test_stylesheet_references_only_existing_fonts() -> None:
    """`css.py` ile `static/fonts/` ayrışmasın."""
    referenced = set(re.findall(r"/static/fonts/([\w.-]+\.woff2)", stylesheet()))
    assert referenced, "Stylesheet hic font bildirmiyor."
    on_disk = {path.name for path in FONT_DIR.glob("*.woff2")}
    assert referenced <= on_disk, f"CSS olmayan fontu istiyor: {referenced - on_disk}"


# ═══════════════════════════════════════════ 5. Türkçe uppercase tuzağı
def test_no_css_uppercase_transform() -> None:
    """Ek B.3: `text-transform: uppercase` Türkçede bozuktur.

    `i` → `I` yapar, `İ` olması gerekir. "iddia" → "IDDIA" (yanlış).
    Küçük etiketlerdeki ayrım bu projede letter-spacing + renk + ağırlık
    ile kuruluyor (`.eyebrow`), büyük harfle değil.
    """
    # CSS yorumlari soyulur: kurali ACIKLAYAN yorum, kuralin ihlali degil.
    css = re.sub(r"/\*.*?\*/", "", stylesheet(), flags=re.DOTALL)
    assert "uppercase" not in css, (
        "Stylesheet'te `text-transform: uppercase` var. Turkcede `i`yi `I` "
        "yapar; `.eyebrow` sinifindaki letter-spacing yaklasimini kullan."
    )
    # Aranan şey `text-transform` değil, `uppercase` DEĞERİ: `capitalize`
    # veya `none` bir sorun değil, Türkçeyi bozan yalnızca uppercase.
    pattern = re.compile(r"text-transform\s*:\s*uppercase")
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in _python_sources()
        if any(pattern.search(v) for v in _emittable_strings(path))
    ]
    assert not offenders, (
        f"`text-transform: uppercase` bulundu: {offenders}. "
        "Turkcede `i` -> `I` yapar; `İ` olmali (Ek B.3)."
    )


# ═══════════════════════════════════════════ 6. tek ikon seti
# Bölüm 13.4: emoji ikon olarak kullanılmaz. Aranan aralıklar emoji ve
# geometrik şekil blokları; Türkçe metin ve tipografik işaretler (—, ·, ⌄)
# bunların dışında kalır.
EMOJI_RANGES = (
    (0x1F300, 0x1FAFF),  # emoji, sembol ve piktogramlar
    (0x2600, 0x27BF),  # çeşitli semboller + dingbat
    (0x1F000, 0x1F2FF),  # ek semboller
)


def _has_emoji(text: str) -> list[str]:
    return [
        f"U+{ord(ch):04X} {ch!r}"
        for ch in text
        if any(low <= ord(ch) <= high for low, high in EMOJI_RANGES)
    ]


# Tarama SUNUM KATMANIYLA sınırlıdır: bir dizenin ekrana veya e-postaya
# çıktığı modüller. LLM prompt modülleri (`editorial/generator.py`) ve
# kontrol işareti tabloları (`editorial/checker.py`) DIŞARIDA:
#
#   * Prompt bir arayüz değildir; oradaki 🟢/🟠 modele kanıt skalasını
#     anlatan bir gösterimdir ve `tests/test_claims.py::
#     test_prompt_file_matches_code` prompt metnini belgeye kilitler —
#     değiştirmek bu testi kırar ve tasarımla ilgisi yoktur.
#   * `checker.SEVERITY_MARK` bir VERİ anahtarıdır; `web/draft.py` onu
#     renge çevirir, ekrana basmaz.
PRESENTATION_MODULES = ("web", "admin")
PRESENTATION_FILES = (
    PACKAGE_DIR / "briefing" / "renderer.py",
    PACKAGE_DIR / "briefing" / "generator.py",
    PACKAGE_DIR / "evidence" / "explain.py",
)


def _presentation_sources() -> list[Path]:
    return [
        path
        for path in _python_sources()
        if path.relative_to(PACKAGE_DIR).parts[0] in PRESENTATION_MODULES
        or path in PRESENTATION_FILES
    ]


def test_ui_layer_uses_no_emoji_as_icons() -> None:
    """Emoji görünümü işletim sistemine göre değişir, renk token'ı almaz
    ve ekran okuyucuda şekil olarak okunur (bkz. `ui/icons.py` başlığı)."""
    scanned = _presentation_sources()
    assert len(scanned) > 10, "Tarama kapsami daralmis — denetim anlamsizlasti."

    offenders: list[str] = []
    for path in scanned:
        found = _has_emoji("".join(_emittable_strings(path)))
        if found:
            offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {found[:5]}")
    assert not offenders, (
        "Arayuzde emoji bulundu:\n  "
        + "\n  ".join(offenders)
        + "\n\nDESIGN.md Bolum 13.4: tek ikon seti — web/ui/icons.py."
    )


def test_every_registered_icon_is_used() -> None:
    """Kullanılmayan ikon `icons.py`'yi bir kütüphaneye çevirir.

    Amaç yalnızca temizlik değil: 60 ikonluk bir dosyada "bunun için bir
    ikon var mıydı?" sorusu yanıtlanamaz hâle gelir ve ekip yenisini ekler.
    """
    blob = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_sources() if path.name != "icons.py"
    )
    # `status_icon` beş `status-*` ikonunu dolaylı çağırır.
    unused = [
        name
        for name in icons.names()
        if not name.startswith("status-")
        and f'"{name}"' not in blob
        and f"'{name}'" not in blob
    ]
    assert not unused, f"Kullanilmayan ikon: {unused}. Ya kullan ya sil."
