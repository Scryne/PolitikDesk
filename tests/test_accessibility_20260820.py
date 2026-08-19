"""Erişilebilirlik regresyon testleri — 20 Ağustos 2026 denetimi.

**Neden bu dosya var.** `design/decisions.md` 15 Ağustos'ta "Lighthouse
A11y: 100" diye kayıtlıydı. 20 Ağustos'ta bağımsız olarak yeniden
ölçüldü: `/feed` **93**, 12 ekranın ortalaması **97,7**, biri (denetim
kuyruğu) **93**. DESIGN.md Bölüm 12 eşiği ≥95.

Yani skor bir kez ölçülüp yazılmış, sonra sessizce gerilemişti. Bir
sayının rapora yazılması onu korumaz; koruyan şey testtir. Bu dosya
skorun dayandığı ÖZELLİKLERİ kilitler.

Düzeltme sonrası: 12/12 ekran **100**.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():  # noqa: ANN201
    """Canlı ekranlar için istemci (test_web.py'deki kalıbın aynısı)."""
    import os

    if not os.environ.get("PD_DATABASE_URL"):
        pytest.skip("PD_DATABASE_URL ayarlı değil — ekran testleri atlandı.")

    from politikdesk.api.main import app

    with TestClient(app) as test_client:
        yield test_client

# ═════════════════════════════════════════════ gezinme bağlantılarının adı
#
# `css.py` dar ekranda `.nav-item span{display:none}` uygular. `display:none`
# öğeyi erişilebilirlik ağacından SİLER; ikonlar `aria-hidden="true"`
# taşıdığı için geriye ad kalmıyordu. Lighthouse `link-name` denetimi 13
# bağlantıda düşüyordu — ekran okuyucuyla uygulama gezilemezdi.


def test_her_gezinme_baglantisinin_erisilebilir_adi_var() -> None:
    from politikdesk.web.ui.shell import NAV, _sidebar

    markup = _sidebar("/feed")
    beklenen = [label for _, items in NAV for _, label, _ in items]
    assert beklenen, "NAV boş — test anlamını yitirmiş"

    for label in beklenen:
        assert f'aria-label="{label}"' in markup or f"aria-label='{label}'" in markup, (
            f"{label!r} gezinme bağlantısında `aria-label` yok. Dar ekranda "
            "etiket `display:none` ile gizlenir ve bağlantı adsız kalır."
        )


def test_gezinme_baglantilari_ikon_only_kalmiyor() -> None:
    """Hiçbir `nav-item` yalnızca `aria-hidden` ikon taşımamalı."""
    from politikdesk.web.ui.shell import _sidebar

    markup = _sidebar("/feed")
    for anchor in re.findall(r"<a class=\"nav-item\".*?</a>", markup, re.S):
        has_label = "aria-label=" in anchor
        # `aria-hidden` OLMAYAN metin var mı?
        text = re.sub(r"<svg.*?</svg>", "", anchor, flags=re.S)
        text = re.sub(r"<[^>]+>", "", text).strip()
        assert has_label or text, f"Adsız gezinme bağlantısı: {anchor[:90]}"


def test_marka_baglantisinin_adi_var() -> None:
    """Kenar çubuğu daraldığında marka metni de gizlenir."""
    from politikdesk.web.ui.shell import _sidebar

    markup = _sidebar("/feed")
    marka = re.search(r'<a class="brand"[^>]*>', markup)
    assert marka is not None
    assert "aria-label=" in marka.group(0), "Marka bağlantısında `aria-label` yok"


def test_aria_label_gorunur_etiketle_ayni() -> None:
    """WCAG 2.5.3 (Label in Name).

    Sesli komutla "Kumanda Odası" diyen kullanıcı ile ekranda yazanı gören
    kullanıcı aynı adı kullanabilmeli. `aria-label` görünür metinden
    farklı olsaydı sesli komut çalışmazdı.
    """
    from politikdesk.web.ui.shell import _sidebar

    markup = _sidebar("/feed")
    for anchor in re.findall(r"<a class=\"nav-item\".*?</a>", markup, re.S):
        m = re.search(r'aria-label="([^"]*)"', anchor)
        assert m is not None
        aria = m.group(1)
        gorunur = re.search(r"<span>([^<]*)</span>", anchor)
        assert gorunur is not None, f"Görünür etiket yok: {anchor[:80]}"
        assert aria == gorunur.group(1), (
            f"`aria-label` ({aria!r}) görünür etiketten ({gorunur.group(1)!r}) farklı"
        )


# ═══════════════════════════════════════════════════ başlık seviyesi düzeni
#
# Sayfalar `h1` ile başlıyor ama kart başlıkları `h3`tü — `h2` atlanıyordu.
# Lighthouse `heading-order` denetimi dokuz ekranda düşüyordu.


def test_kart_basligi_h2_uretir() -> None:
    from politikdesk.web.ui.components import card

    markup = card("gövde", title="Kaynak sağlığı")
    assert "<h2" in markup, "Kart başlığı `h2` olmalı (h1'den sonraki seviye)"
    assert "<h3" not in markup, "`h3` seviye atlıyor"


def test_kart_basligi_gorsel_boyutu_korur() -> None:
    """Seviye SEMANTİK, boyut GÖRSEL karardır — ikisi karıştırılmamalı.

    `.h3` sınıfı olmadan başlık `h2` boyutuna (20px) sıçrardı; ölçüldü:
    eski `h3` ve yeni `h2.h3` birebir aynı hesaplanıyor (16px/24px/600).
    """
    from politikdesk.web.ui.components import card

    markup = card("gövde", title="Kaynak sağlığı")
    assert "h3" in markup, "`.h3` sınıfı düşmüş — kart başlığı büyüyecek"


def test_kart_basligi_kacisi_korunuyor() -> None:
    """Seviye değişimi kaçışı bozmamalı."""
    from politikdesk.web.ui.components import card

    markup = card("gövde", title='<script>alert("x")</script>')
    assert "<script>" not in markup


@pytest.mark.db
@pytest.mark.parametrize(
    "path",
    ["/feed", "/admin/", "/admin/metrics", "/memory", "/archive", "/accountability"],
)
def test_ekranlarda_baslik_seviyesi_atlanmiyor(client, path: str) -> None:  # noqa: ANN001
    """DESIGN.md Bölüm 12: "başlık seviyeleri atlanmaz"."""
    body = client.get(path).text
    seviyeler = [int(m) for m in re.findall(r"<h([1-6])[\s>]", body)]
    if not seviyeler:
        pytest.skip(f"{path}: başlık yok")

    assert seviyeler[0] == 1, f"{path}: sayfa `h1` ile başlamıyor ({seviyeler[:3]})"
    for onceki, sonraki in zip(seviyeler, seviyeler[1:], strict=False):
        assert sonraki <= onceki + 1, (
            f"{path}: h{onceki} -> h{sonraki} seviye atlıyor"
        )


@pytest.mark.db
def test_ekranlarda_adsiz_baglanti_yok(client) -> None:  # noqa: ANN001
    """Lighthouse `link-name` denetiminin kod tarafındaki karşılığı."""
    body = client.get("/feed").text
    adsiz = []
    for anchor in re.findall(r"<a\b[^>]*>.*?</a>", body, re.S):
        if "aria-label=" in anchor or "aria-labelledby=" in anchor:
            continue
        govde = re.sub(r"<svg.*?</svg>", "", anchor, flags=re.S)
        govde = re.sub(r"<[^>]+>", "", govde).strip()
        if not govde:
            adsiz.append(anchor[:100])
    assert not adsiz, f"{len(adsiz)} adsız bağlantı: {adsiz[:3]}"


# ═══════════════════════════════════════════════════════ dokunma hedefi
#
# WCAG 2.5.8 (AA): etkileşimli öğe en az 24x24 CSS px olmalı. Tablo
# hücresindeki bağlantılar küçük punto olduğu için altında kalıyordu
# (denetim kuyruğunda 100, vaatler ekranında 8 öğe).


def test_tablo_hucresi_baglantilarinda_asgari_dokunma_hedefi_var() -> None:
    from politikdesk.web.ui.css import stylesheet

    css = stylesheet()
    kural = re.search(r"tbody td a\{[^}]*\}", css)
    assert kural is not None, "`tbody td a` kuralı yok — dokunma hedefi korumasız"
    assert "min-height:24px" in kural.group(0).replace(" ", ""), (
        "Tablo bağlantılarında asgari 24px yükseklik yok (WCAG 2.5.8)"
    )
