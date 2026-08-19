"""Faz 7 — CSP nonce mimarisinin kapıları (ADR-011).

Bu dosya iki tür kapı içerir ve ikisi de gereklidir:

* **Davranışsal invariantlar** — üretilen gerçek yanıt üzerinden ölçülür.
  "Nonce başlıkla eşleşiyor mu", "iki istek aynı nonce'u alıyor mu" gibi
  sorular ancak yanıt üretilerek cevaplanabilir.
* **Yüzey kapıları** — `unsafe-inline` ve satır içi olay işleyicilerinin
  geri sızmasını engeller. Bu bir REGRESYON kapısıdır: Faz 7'nin kazanımı
  tek bir `onclick=` ile geri alınabilir ve bu sessizce olur (düğme
  tarayıcıda çalışmaz, sunucuda hiçbir iz kalmaz).

### Yüzey kapısı neden HTML üzerinden ölçülüyor

Kaynak kodu taramak yanlış alarm üretir: yorumlar, docstring'ler ve
`ingestion/adapters/sayistay.py`'deki *ayrıştırıcı* regex'i (dış siteden
`onclick` OKUR, üretmez) hepsi eşleşirdi. Önceki fazlarda "hep açık alarm"
sorununun kaynağı tam olarak buydu.

Üretilen HTML'i taramak bu sınıfı tamamen ortadan kaldırır: bir yorum
sayfaya basılmıyorsa zaten önemsizdir, basılıyorsa gerçekten oradadır.
Ölçtüğümüz şey tarayıcının gördüğü şeydir.
"""

from __future__ import annotations

import html as html_mod
import json
import re

import pytest
from fastapi.testclient import TestClient

# Depodaki her HTML ekranı. `scripts/ui_check.py::PAGES` ile aynı liste;
# yeni sayfa açan oraya da buraya da bir satır ekler.
HTML_PAGES: tuple[str, ...] = (
    "/feed",
    "/briefing",
    "/onboarding/profile",
    "/admin/",
    "/admin/metrics",
    "/admin/review/",
    "/admin/calendar/",
    "/accountability",
    "/memory",
    "/promises",
    "/archive",
    "/war-room",
)

# Yasak satır içi işleyiciler. Liste HTML'in tamamı değil; gerçekten
# kullanılmış olan ve kullanılması muhtemel olan olaylar.
INLINE_HANDLER_RE = re.compile(
    r"\bon(click|dblclick|change|input|submit|load|error|focus|blur"
    r"|keydown|keyup|keypress|mouseover|mouseenter|mouseleave|wheel|scroll|toggle)\s*=",
    re.IGNORECASE,
)

NONCE_IN_CSP_RE = re.compile(r"'nonce-([A-Za-z0-9_+/=-]+)'")
SCRIPT_TAG_RE = re.compile(r"<script(?P<attrs>[^>]*)>", re.IGNORECASE)


@pytest.fixture(scope="module")
def client() -> TestClient:
    from politikdesk.api.main import app

    return TestClient(app)


def _script_nonces(markup: str) -> list[str | None]:
    """Her `<script>` etiketinin nonce'u; taşımayan için `None`."""
    out: list[str | None] = []
    for match in SCRIPT_TAG_RE.finditer(markup):
        attrs = match.group("attrs")
        if "src=" in attrs:  # harici betik — nonce gerekmez
            continue
        found = re.search(r'nonce="([^"]*)"', attrs)
        out.append(found.group(1) if found else None)
    return out


# ─────────────────────────────────────────── 1. nonce yaşam döngüsü
def test_her_html_istegi_yeni_nonce_alir(client: TestClient) -> None:
    """§8.1 + §8.3: nonce request başına üretilir ve paylaşılmaz."""
    seen = set()
    for _ in range(12):
        csp = client.get("/feed").headers["Content-Security-Policy"]
        match = NONCE_IN_CSP_RE.search(csp)
        assert match is not None, "CSP nonce taşımıyor."
        seen.add(match.group(1))

    assert len(seen) == 12, f"Nonce istekler arasında paylaşılıyor: {len(seen)}/12 benzersiz."


def test_nonce_tahmin_edilemez_uzunlukta(client: TestClient) -> None:
    """Nonce süreç başında değil, kriptografik olarak üretilmeli."""
    csp = client.get("/feed").headers["Content-Security-Policy"]
    nonce = NONCE_IN_CSP_RE.search(csp).group(1)  # type: ignore[union-attr]

    # 32 bayt token_urlsafe → 43 karakter. 22'nin (16 bayt) altı zayıf sayılır.
    assert len(nonce) >= 22, f"Nonce çok kısa: {len(nonce)} karakter."
    # `secrets` alfabesi. Boşluk/tırnak başlığı veya özniteliği kırardı.
    assert re.fullmatch(r"[A-Za-z0-9_-]+", nonce), f"Nonce beklenmedik alfabede: {nonce!r}"


@pytest.mark.parametrize("path", HTML_PAGES)
def test_csp_nonce_ile_html_nonce_ayni_yanitta_eslesir(client: TestClient, path: str) -> None:
    """§8.2: aynı yanıtın başlığındaki ve HTML'indeki nonce aynı olmalı.

    Bu, mimarinin can damarı: ikisi ayrı üretilirse sayfa sessizce
    betiksiz kalır — HTML gelir, hiçbir düğme çalışmaz.
    """
    resp = client.get(path)
    assert resp.status_code == 200, f"{path} → {resp.status_code}"

    header_nonce = NONCE_IN_CSP_RE.search(resp.headers["Content-Security-Policy"])
    assert header_nonce is not None, f"{path}: CSP nonce yok."

    nonces = _script_nonces(resp.text)
    assert nonces, f"{path}: hiç satır içi betik bulunamadı — sayfa iskeleti değişmiş olabilir."
    assert None not in nonces, f"{path}: nonce'suz satır içi betik var — tarayıcı onu bloklar."
    assert set(nonces) == {header_nonce.group(1)}, (
        f"{path}: HTML nonce'u başlıktakiyle eşleşmiyor."
    )


def test_iki_farkli_istegin_nonce_lari_capraz_gecerli_degildir(client: TestClient) -> None:
    """§9: başka bir isteğin nonce'u bu yanıtta geçersiz olmalı."""
    first = client.get("/feed")
    second = client.get("/feed")

    first_nonce = _script_nonces(first.text)[0]
    second_csp = second.headers["Content-Security-Policy"]

    assert first_nonce is not None
    assert first_nonce not in second_csp, (
        "Bir isteğin nonce'u başka bir yanıtın CSP'sinde geçerli — nonce paylaşılıyor."
    )


def test_nonce_loglara_girmez(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    """§8.5: nonce log'a yazılmamalı."""
    import logging

    with caplog.at_level(logging.DEBUG):
        resp = client.get("/feed")

    nonce = NONCE_IN_CSP_RE.search(resp.headers["Content-Security-Policy"]).group(1)  # type: ignore[union-attr]
    assert nonce not in caplog.text, "Nonce loglara sızıyor."


def test_nonce_http_baglami_disinda_uretilmez() -> None:
    """§8.4/8.6: nonce global state'e yazılmaz, kullanıcı girdisinden türetilmez.

    HTTP isteği dışında `page()` çağrılırsa (Celery görevi, brifing üretimi)
    nonce özniteliği HİÇ basılmamalı — bayat bir nonce basmaktansa hiç
    basmamak doğrudur.
    """
    from politikdesk.web.ui.nonce import current_nonce, nonce_attr

    assert current_nonce() == ""
    assert nonce_attr() == ""


def test_nonce_uretimi_kullanici_girdisinden_bagimsizdir(client: TestClient) -> None:
    """§8.6: nonce kullanıcı girdisinden türetilmez.

    Aynı sorgu dizesiyle iki istek farklı nonce almalı; nonce girdinin bir
    fonksiyonu olsaydı ikisi eşit çıkardı ve tahmin edilebilir olurdu.
    """
    query = "/feed?f=ready&limit=7"
    first = NONCE_IN_CSP_RE.search(client.get(query).headers["Content-Security-Policy"])
    second = NONCE_IN_CSP_RE.search(client.get(query).headers["Content-Security-Policy"])
    assert first is not None and second is not None
    assert first.group(1) != second.group(1)


# ─────────────────────────────────────────── 2. CSP politikası
def test_script_src_unsafe_inline_icermez(client: TestClient) -> None:
    """§8.8 + §17: `unsafe-inline` script-src'de BULUNMAZ."""
    csp = client.get("/feed").headers["Content-Security-Policy"]
    script_src = next(d for d in csp.split(";") if d.strip().startswith("script-src"))

    assert "unsafe-inline" not in script_src, f"script-src gevşetilmiş: {script_src}"
    assert "unsafe-eval" not in script_src, f"script-src'e unsafe-eval eklenmiş: {script_src}"
    assert "'nonce-" in script_src
    assert "'self'" in script_src


def test_csp_nin_diger_guvenlik_direktifleri_korunuyor(client: TestClient) -> None:
    """Faz 7 yalnızca script-src'ye dokunmalı; kalan direktifler aynı kalmalı."""
    csp = client.get("/feed").headers["Content-Security-Policy"]

    for directive in (
        "default-src 'self'",
        "style-src 'self' 'unsafe-inline'",  # bilinen sınırlama — ADR-011
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "form-action 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'self'",
    ):
        assert directive in csp, f"Direktif kaybolmuş veya değişmiş: {directive}"


def test_csp_her_yanit_turunde_nonce_tasir(client: TestClient) -> None:
    """§2: hata, JSON, sağlık ve yönlendirme yollarında da başlık tam olmalı."""
    responses = {
        "html_404": client.get("/event/999999999"),
        "json_api": client.get("/api/memory/actors?q=zz&limit=1"),
        "health": client.get("/health/live"),
        "static": client.get("/static/fonts/inter-tight-latin.woff2"),
    }
    for label, resp in responses.items():
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "unsafe-inline" not in csp.split("style-src")[0], f"{label}: script-src gevşek."
        assert NONCE_IN_CSP_RE.search(csp), f"{label}: CSP nonce taşımıyor."


# ─────────────────────────────────────────── 3. yüzey kapıları
@pytest.mark.parametrize("path", HTML_PAGES)
def test_uretilen_html_satir_ici_olay_isleyicisi_icermez(client: TestClient, path: str) -> None:
    """§17: inline event handler sayısı 0.

    Nonce bunları KURTARMAZ — `unsafe-inline` kalktığı an tarayıcı satır içi
    öznitelik işleyicilerini çalıştırmaz. Geri eklenen bir tanesi sessizce
    ölü bir düğme bırakır.
    """
    markup = client.get(path).text
    hits = INLINE_HANDLER_RE.findall(markup)
    assert not hits, f"{path}: satır içi olay işleyici(leri) geri gelmiş: {sorted(set(hits))}"


@pytest.mark.parametrize("path", HTML_PAGES)
def test_uretilen_html_javascript_url_icermez(client: TestClient, path: str) -> None:
    """`javascript:` URL'leri de script-src tarafından reddedilir."""
    markup = client.get(path).text.lower()
    assert "javascript:" not in markup, f"{path}: `javascript:` URL'i kalmış."


@pytest.mark.parametrize("path", HTML_PAGES)
def test_uretilen_html_de_nonce_suz_calisan_betik_yoktur(client: TestClient, path: str) -> None:
    """§17: nonce'suz executable inline script sayısı 0."""
    assert None not in _script_nonces(client.get(path).text), f"{path}: nonce'suz betik var."


def test_csp_bypass_araclari_koda_girmemis(client: TestClient) -> None:
    """§7: `eval` / `new Function` gibi yollar CSP'yi anlamsız kılardı."""
    markup = client.get("/feed").text
    for gadget in ("eval(", "new Function(", "document.write("):
        assert gadget not in markup, f"CSP bypass aracı sayfaya girmiş: {gadget}"


# ─────────────────────────────────────────── 4. dağıtıcının güvenliği
def test_dagitici_yalnizca_kayitli_eylemleri_cagirir() -> None:
    """§7 + saldırgan gözü: dağıtıcı bir `eval` gadget'ına dönüşmemeli.

    Eylem adı `window` üzerinde çözülseydi `data-pd-click="eval"` +
    `data-pd-args='["kod"]'` yazabilen bir enjeksiyon, CSP'yi tamamen
    atlatarak kendi kodunu çalıştırırdı. Kayıt defteri prototipsiz olmalı
    ve yalnızca açıkça kaydedilmiş adlar çağrılabilmeli.
    """
    from politikdesk.web.ui.shell import _DISPATCH_JS

    assert "Object.create(null)" in _DISPATCH_JS, "Kayıt defteri prototipsiz değil."
    assert "window.pdActions[" in _DISPATCH_JS
    assert "typeof fn !== 'function'" in _DISPATCH_JS, "Kayıtsız ad için çıkış kapısı yok."
    # Ad ASLA `window` üzerinden çözülmemeli.
    assert "window[" not in _DISPATCH_JS
    # Argümanlar VERİ olarak ayrıştırılır, kod olarak değil.
    assert "JSON.parse" in _DISPATCH_JS
    assert "eval" not in _DISPATCH_JS
    assert "new Function" not in _DISPATCH_JS


def test_dagitici_bozuk_argumanlarda_sessizce_durur() -> None:
    """Bozuk JSON istisna fırlatıp sayfanın kalan davranışını kırmamalı."""
    from politikdesk.web.ui.shell import _DISPATCH_JS

    assert "try { args = JSON.parse(raw); } catch (e) { return; }" in _DISPATCH_JS
    assert "if (!Array.isArray(args)) return;" in _DISPATCH_JS


def test_eylem_argumanlari_kod_degil_veri_olarak_gomulur() -> None:
    """`action_attrs` bir JS ifadesi değil, kaçırılmış JSON üretmeli."""
    from politikdesk.web.ui.components import action_attrs

    # Kapanış denemesi içeren kötü niyetli metin özniteliği kıramamalı.
    hostile = '"><script>alert(1)</script>'
    out = action_attrs("copy", hostile, "Etiket")

    assert "<script>" not in out, "Kaçış yapılmamış — öznitelikten kaçılabiliyor."
    assert 'data-pd-click="copy"' in out

    raw = re.search(r'data-pd-args="([^"]*)"', out)
    assert raw is not None
    assert json.loads(html_mod.unescape(raw.group(1))) == [hostile, "Etiket"]


def test_desteklenmeyen_olay_adi_sessizce_gecmez() -> None:
    """Dağıtıcının dinlemediği bir olay adı ölü işaretleme üretirdi."""
    from politikdesk.web.ui.components import action_attrs

    with pytest.raises(ValueError, match="Desteklenmeyen"):
        action_attrs("copy", event="mouseover")


def test_buton_hem_href_hem_eylem_alamaz() -> None:
    """`<a>` olarak basılan butonda eylem sessizce düşerdi."""
    from politikdesk.web.ui.components import button

    with pytest.raises(ValueError, match="birlikte kullanılamaz"):
        button("Test", href="/feed", action="copy")


def test_her_kullanilan_eylem_kayitlidir(client: TestClient) -> None:
    """İşaretlemedeki her eylem adının bir `pdAction(...)` kaydı olmalı.

    Kayıtsız bir ad sessiz arızadır: düğme görünür, tıklanır, hiçbir şey
    olmaz ve ne konsolda ne sunucuda iz kalır.
    """
    used: set[str] = set()
    registered: set[str] = set()

    for path in HTML_PAGES:
        markup = client.get(path).text
        used |= set(re.findall(r'data-pd-(?:click|input|change)="([^"]+)"', markup))
        registered |= set(re.findall(r"pdAction\(\s*'([^']+)'", markup))

    missing = used - registered
    assert not missing, f"İşaretlemede var ama kaydı yok: {sorted(missing)}"
