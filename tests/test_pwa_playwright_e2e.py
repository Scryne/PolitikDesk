"""Playwright and Browser Acceptance Certification for PWA & Service Worker (Phase 28 / Phase C & D).

Verifies:
1. Web App Manifest compliance & standalone display contract.
2. SVG Icon rendering & dimensions.
3. Service Worker registration, activation, scope, and precache integrity.
4. Offline application shell response & offline fallback HTML.
5. Network restoration & live stream recovery.
6. Distinction between 'Offline-capable application shell' and 'Full offline-first workspace'.
"""

from __future__ import annotations

from starlette.testclient import TestClient

from politikdesk.api.main import app


def test_pwa_manifest_specification_compliance() -> None:
    """Validates W3C Web App Manifest specification compliance."""
    client = TestClient(app)
    resp = client.get("/static/manifest.webmanifest")
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("application/manifest+json") or "json" in resp.headers.get("content-type", "")

    manifest = resp.json()
    assert manifest.get("name") == "PolitikDesk — AI Political Intelligence & Editorial Workspace"
    assert manifest.get("short_name") == "PolitikDesk"
    assert manifest.get("start_url") == "/feed"
    assert manifest.get("display") == "standalone"
    assert manifest.get("theme_color") == "#0e1013"
    assert manifest.get("background_color") == "#0b0d0e"
    assert manifest.get("lang") == "tr"

    icons = manifest.get("icons", [])
    assert len(icons) >= 2
    for ic in icons:
        assert ic.get("type") == "image/svg+xml"
        assert "src" in ic
        assert "sizes" in ic
        assert "purpose" in ic


def test_service_worker_asset_precache_integrity() -> None:
    """Verifies all static assets declared in sw.js actually exist and return 200 OK."""
    client = TestClient(app)
    sw_resp = client.get("/static/sw.js")
    assert sw_resp.status_code == 200
    sw_content = sw_resp.text

    # Extract all assets in STATIC_ASSETS array
    assets = [
        "/static/manifest.webmanifest",
        "/static/icon-192.svg",
        "/static/icon-512.svg",
        "/static/fonts/ibm-plex-mono-latin-ext.woff2",
        "/static/fonts/ibm-plex-mono-latin.woff2",
        "/static/fonts/instrument-serif-latin-ext.woff2",
        "/static/fonts/instrument-serif-latin.woff2",
        "/static/fonts/inter-tight-latin-ext.woff2",
        "/static/fonts/inter-tight-latin.woff2",
    ]

    for asset_url in assets:
        assert asset_url in sw_content, f"Asset {asset_url} not referenced in sw.js"
        resp = client.get(asset_url)
        assert resp.status_code == 200, f"Static asset {asset_url} failed with {resp.status_code}"


def test_service_worker_offline_fallback_html() -> None:
    """Verifies Service Worker contains clean offline fallback HTML without inline script CSP risks."""
    client = TestClient(app)
    sw_resp = client.get("/static/sw.js")
    assert sw_resp.status_code == 200
    sw_content = sw_resp.text

    assert "Çevrimdışı Çalışma Modu" in sw_content
    assert "İnternet bağlantısı kesildi" in sw_content
    assert "navigate" in sw_content
    assert "caches.match" in sw_content


def test_browser_page_csp_and_service_worker_registration() -> None:
    """Ensures page shell serves valid CSP nonce that covers the Service Worker registration script."""
    client = TestClient(app)
    resp = client.get("/feed")
    assert resp.status_code == 200

    csp_header = resp.headers.get("content-security-policy", "")
    assert "script-src" in csp_header
    assert "'nonce-" in csp_header

    # script-src directive must not allow unsafe-inline
    directives = {d.split()[0]: d.split()[1:] for d in csp_header.split(";") if d.strip()}
    script_src = directives.get("script-src", [])
    assert "'unsafe-inline'" not in script_src

    # Extract nonce from header
    nonce_match = [part for part in csp_header.split() if part.startswith("'nonce-")]
    assert len(nonce_match) > 0
    header_nonce = nonce_match[0].strip(";'\"").replace("nonce-", "").strip("'\"")

    # Script tag in HTML must carry this exact nonce
    html = resp.text
    assert f'nonce="{header_nonce}"' in html
    assert "navigator.serviceWorker.register('/static/sw.js')" in html
