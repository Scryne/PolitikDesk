"""SVG Grafik, UI Güvenliği (XSS Koruması) ve Mobil Stillere İlişkin Testler."""

from __future__ import annotations

from politikdesk.web.ui.charts import economic_indicator_card, sparkline_svg
from politikdesk.web.ui.components import SafeString, _attrs, esc, esc_attr, mark_safe
from politikdesk.web.ui.css import stylesheet


def test_safestring_and_esc_immunity() -> None:
    raw_xss = '<script>alert("xss")</script>'
    escaped = esc(raw_xss)
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped

    safe_markup = mark_safe('<span class="badge">Güvenli</span>')
    assert isinstance(safe_markup, SafeString)
    # Çift kaçışa uğramamalı
    assert esc(safe_markup) == '<span class="badge">Güvenli</span>'


def test_esc_attr_neutralizes_protocols_and_quotes() -> None:
    # JavaScript URI saldırısı etkisizleşmeli
    assert esc_attr("javascript:alert(1)") == "#"
    assert esc_attr("JAVASCRIPT: alert(1)") == "#"
    assert esc_attr("vbscript:msgbox(1)") == "#"
    assert esc_attr("data:text/html,<script>alert(1)</script>") == "#"

    # Güvenli URL ve değerler düzgün kaçırılmalı
    assert esc_attr('https://example.com/search?q="test"') == 'https://example.com/search?q=&quot;test&quot;'


def test_attrs_escaping() -> None:
    rendered = _attrs(cls="my-class", href='javascript:alert("hacked")', title='Sayfa "1"')
    assert 'class="my-class"' in rendered
    assert 'href="#"' in rendered
    assert 'title="Sayfa &quot;1&quot;"' in rendered


def test_sparkline_svg_generation() -> None:
    # 1. Boş veri
    empty_svg = sparkline_svg([])
    assert "<svg" in empty_svg
    assert "stroke-dasharray" in empty_svg

    # 2. Tek noktalı veri
    single_svg = sparkline_svg([45.0])
    assert "<svg" in single_svg
    assert "<circle" in single_svg

    # 3. Düz çizgi (tüm değerler eşit)
    flat_svg = sparkline_svg([50.0, 50.0, 50.0, 50.0])
    assert "<path" in flat_svg
    assert "<svg" in flat_svg

    # 4. Dinamik değer serisi
    trend_svg = sparkline_svg([40.0, 42.5, 45.0, 48.0, 50.0], width=120, height=30)
    assert '<svg width="120" height="30"' in trend_svg
    assert "<path" in trend_svg


def test_economic_indicator_card_rendering() -> None:
    card_html = economic_indicator_card(
        title="TCMB Politika Faizi",
        current_value="%45.00",
        unit="",
        history=[40.0, 42.5, 45.0, 45.0],
        change_text="Sabit",
        is_anomaly=True,
        source_name="TCMB",
    )
    assert "TCMB Politika Faizi" in card_html
    assert "%45.00" in card_html
    assert "Anomali" in card_html
    assert "sparkline" in card_html


def test_responsive_mobile_css_in_stylesheet() -> None:
    css = stylesheet()
    assert "@media (max-width:640px)" in css
    assert "@media (max-width:768px)" in css
    assert ".responsive-table" in css
    assert ".table-cards" in css
    assert "min-height:44px" in css


def test_security_headers_in_response() -> None:
    from fastapi.testclient import TestClient

    from politikdesk.api.main import app

    client = TestClient(app)
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "geolocation=()" in resp.headers.get("Permissions-Policy", "")


def test_content_security_policy_enforces_the_no_cdn_promise() -> None:
    """DESIGN.md 6.1 "sıfır harici CSS/CDN" sözü tarayıcıda da zorlanmalı.

    Söz şimdiye dek yalnızca disiplinle tutuluyordu; yanlışlıkla eklenen
    bir CDN bağlantısı sessizce çalışırdı. `default-src 'self'` onu
    tarayıcı düzeyinde reddeder.
    """
    from fastapi.testclient import TestClient

    from politikdesk.api.main import app

    client = TestClient(app)
    csp = client.get("/health/live").headers.get("Content-Security-Policy", "")

    assert "default-src 'self'" in csp
    # XSS başarılı olsa bile veri dışarı sızdıramasın.
    assert "connect-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    # Harici kaynak izni HİÇBİR direktifte olmamalı.
    assert "http://" not in csp
    assert "https://" not in csp
    assert "*" not in csp


def test_command_palette_never_writes_untrusted_names_as_html() -> None:
    """Komuta paleti aktör adlarını DB'den okur; o adlar NER ile DIŞ
    KAYNAKLI makale metninden çıkarılır. innerHTML'e verilmeleri saklı
    XSS olurdu."""
    from politikdesk.web.ui.shell import _CMD_JS

    assert "a.innerHTML" not in _CMD_JS
    assert "titleEl.textContent = item.title" in _CMD_JS


def test_command_palette_reads_the_actual_search_contract() -> None:
    """Palet, sunucunun GERÇEKTEN döndürdüğü anahtarları okumalı.

    Bir dönem `data.items` / `act.actor_name` okunuyordu; sözleşme
    `{actors: [{name, entity_type}]}` olduğu için palet aktör aramasını
    SESSİZCE hiç göstermiyordu — hata da vermiyordu, sonuç da yoktu.

    Faz 8.2'de palet tek uca (`/api/search`) taşındı ve sözleşme
    `{results: [{kind, group, title, subtitle, href}]}` oldu. Ayrı uç ve
    ayrı okuma kodu, aynı sessiz arızanın yedi kopyası olurdu. Sözleşmenin
    kendisi `tests/test_command_palette.py` içinde uçtan uca ölçülüyor;
    burada ölçülen, JS'in o anahtarları okuduğudur.
    """
    from politikdesk.web.search import SearchHit
    from politikdesk.web.ui.shell import _CMD_JS

    sozlesme = SearchHit("event", "x", "y", "/z").as_dict()
    assert set(sozlesme) == {"kind", "group", "title", "subtitle", "href"}

    assert "/api/search?q=" in _CMD_JS
    assert "data.results" in _CMD_JS
    for anahtar in ("item.title", "item.subtitle", "item.href", "item.group"):
        assert anahtar in _CMD_JS, f"Palet '{anahtar}' anahtarını okumuyor."

    # Eski sözleşmenin anahtarları geri sızmamalı.
    assert "data.actors" not in _CMD_JS
    assert "actor_name" not in _CMD_JS
    assert "item.hint" not in _CMD_JS


def test_quick_draft_never_interpolates_draft_body_into_markup() -> None:
    """Taslak gövdesi şablona gömülmemeli.

    İki arıza birden vardı: tek tırnaklı `onclick` özniteliğine
    `JSON.stringify(body)` gömülüyordu (Türkçe kesme işareti düğmeyi
    bozuyordu) ve gövde `<textarea>` içine innerHTML ile yazılıyordu.
    """
    from fastapi.testclient import TestClient

    from politikdesk.api.main import app

    html = TestClient(app).get("/feed").text

    assert "JSON.stringify(body)" not in html
    # Metin alanı işaretleme olarak KURULMAZ; gövde ona değer olarak verilir.
    assert "feed-tweet-textarea" in html
    assert "<textarea class=\\\"feed-tweet-textarea" not in html
    assert "area.value = body" in html
    assert "box.replaceChildren()" in html


def test_server_rendered_copy_button_survives_turkish_apostrophes() -> None:
    """Kesme işareti içeren taslak, kopyala düğmesini bozmamalı.

    Bu, canlı veriyle yakalanmış bir arızadır: `onclick` özniteliği tek
    tırnakla açılıyor ve gövde `json.dumps` ile gömülüyordu. `json.dumps`
    tek tırnağı kaçırmaz; Türkçede kesme işareti kural olduğu için
    ("Silivri'deki", "Mahkemesi'nde") düğme pratikte HER taslakta
    bozuluyordu ve kalan metin işaretleme olarak ayrıştırılıyordu.

    Faz 7'de taşıyıcı `onclick` değil `data-pd-args` oldu; arıza sınıfı
    aynı kaldığı için test de taşındı — ve TAM TUR (round-trip) doğrulaması
    yaparak güçlendirildi: özniteliği tarayıcının yaptığı gibi çözüp JSON'ı
    ayrıştırıyoruz ve metnin bit bit aynı çıktığını görüyoruz. Eski hâli
    yalnızca "kaçırılmış mı" diye bakıyordu.
    """
    import html as html_mod
    import json
    import re

    from politikdesk.web.feed import _tweet_module

    body = "Mahkeme kararı Silivri'deki salonda okundu; İBB'nin itirazı reddedildi."
    markup = _tweet_module(
        {
            "id": 7,
            "latest_draft": {"id": 3, "body": body, "is_grounded": True, "angle": "inform"},
        }
    )

    # Kopyala düğmesinin argümanları. Öznitelik çift tırnakla açılır;
    # ham tek tırnak İÇERİDE kalmamalı, `&#x27;` olarak kaçırılmalı.
    raw = re.search(r'data-pd-click="copy" data-pd-args="([^"]*)"', markup)
    assert raw is not None, "Kopyala düğmesi eylem özniteliğini taşımıyor."
    assert "&#x27;" in raw.group(1), "Kesme işareti kaçırılmamış."

    # Tarayıcının yaptığı: öznitelik varlıklarını çöz, sonra JSON'ı ayrıştır.
    args = json.loads(html_mod.unescape(raw.group(1)))
    assert args == [body, "X Tweeti"], "Metin tam turdan aynı çıkmadı."


def test_pd_toast_does_not_use_inner_html() -> None:
    """IMP-01 Regresyon Testi: pdToast metinleri innerHTML ile basmamalı (DOM XSS savunması)."""
    from politikdesk.web.ui.shell import _THEME_JS

    assert "t.innerHTML" not in _THEME_JS
    assert "textContent" in _THEME_JS
    assert "replaceChildren" in _THEME_JS


def test_security_headers_present_on_short_circuited_auth_and_csrf_rejections(
    monkeypatch,
) -> None:
    """IMP-04 Regresyon Testi: _TokenAuthMiddleware ve _CSRFProtectionMiddleware erken 401/403 döndürdüğünde dahi güvenlik başlıkları eklenmelidir."""
    from fastapi.testclient import TestClient

    from politikdesk.api.main import app
    from politikdesk.config import get_settings

    client = TestClient(app)

    # 1. 401 Kimlik Doğrulama Reddi
    monkeypatch.setenv("PD_API_TOKEN", "secret-token-123")
    get_settings.cache_clear()
    resp_401 = client.get("/api/profile")
    assert resp_401.status_code == 401
    assert resp_401.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp_401.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert resp_401.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    # 2. 403 Geçersiz Belirteç Reddi
    resp_403_auth = client.get("/api/profile", headers={"X-API-Token": "wrong-token"})
    assert resp_403_auth.status_code == 403
    assert resp_403_auth.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp_403_auth.headers.get("X-Frame-Options") == "SAMEORIGIN"

    # 3. 403 CSRF Reddi (Cross-origin POST)
    monkeypatch.delenv("PD_API_TOKEN", raising=False)
    get_settings.cache_clear()
    resp_403_csrf = client.post(
        "/feed",
        headers={"Origin": "https://malicious-site.com", "Host": "politikdesk.local"},
    )
    assert resp_403_csrf.status_code == 403
    assert resp_403_csrf.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp_403_csrf.headers.get("X-Frame-Options") == "SAMEORIGIN"


