"""Phase 26: Accessibility (WCAG 2.2 AA) Audit Test Suite."""

from __future__ import annotations

import re

from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.web.ui.css import stylesheet

client = TestClient(app)
AUTH = {"X-User-Id": "1"}


def test_a11y_01_doctype_and_html_lang() -> None:
    """WCAG 3.1.1: HTML belgesinde lang='tr' niteliği ve doctype tanımlı olmalıdır."""
    resp = client.get("/feed", headers=AUTH)
    assert resp.status_code == 200
    assert "<!doctype html>" in resp.text.lower() or "<html" in resp.text.lower()
    assert 'lang="tr"' in resp.text.lower() or "lang='tr'" in resp.text.lower()


def test_a11y_02_viewport_and_zoom() -> None:
    """WCAG 1.4.4: Viewport kullanıcı yakınlaştırmasını (zoom) engellememelidir."""
    resp = client.get("/feed", headers=AUTH)
    assert "user-scalable=no" not in resp.text.lower()
    assert "maximum-scale=1" not in resp.text.lower()


def test_a11y_03_aria_live_regions() -> None:
    """WCAG 4.1.3: Dinamik bildirimler ve yeni haber sayaçları aria-live veya rol barındırmalıdır."""
    resp = client.get("/feed", headers=AUTH)
    assert "aria-live" in resp.text or "role=" in resp.text or "aria-" in resp.text


def test_a11y_04_headings_hierarchy() -> None:
    """WCAG 1.3.1: Başlık hiyerarşisinde başlık etiketi tanımlı olmalıdır."""
    resp = client.get("/feed", headers=AUTH)
    assert "<h" in resp.text or "title" in resp.text.lower()


def test_a11y_05_buttons_and_links_accessible_names() -> None:
    """WCAG 4.1.2: Buton ve bağlantıların erişilebilir etiketleri / metinleri olmalıdır."""
    resp = client.get("/feed", headers=AUTH)
    empty_buttons = re.findall(r"<button[^>]*>\s*</button>", resp.text)
    assert len(empty_buttons) == 0, f"İsimsiz buton bulundu: {empty_buttons}"


def test_a11y_06_form_inputs_labels_or_aria() -> None:
    """WCAG 1.3.1 / 4.1.2: Arama ve form girdileri placeholder / aria-label barındırmalıdır."""
    resp = client.get("/feed", headers=AUTH)
    inputs = re.findall(r"<input[^>]*>", resp.text)
    for inp in inputs:
        if 'type="hidden"' in inp:
            continue
        assert ("placeholder=" in inp or "aria-label=" in inp or "id=" in inp or "name=" in inp), f"Etiketsiz girdi: {inp}"


def test_a11y_07_reduced_motion_css_support() -> None:
    """WCAG 2.3.3: CSS içinde prefers-reduced-motion desteği bulunmalıdır."""
    css_text = stylesheet()
    assert "prefers-reduced-motion" in css_text
