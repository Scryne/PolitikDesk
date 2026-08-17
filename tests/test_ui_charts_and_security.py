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
