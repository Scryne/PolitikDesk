"""PolitikDesk — Adversarial Claim-to-Evidence Verification Test Suite (V3).

Principal Engineer + AppSec + QA + Reliability verification test matrix.
Converts all qualitative claims into strict, assertion-based regression tests.
"""

from __future__ import annotations

import secrets
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.config import get_settings
from politikdesk.ingestion.http import HttpClient, UnsafeUrlError, validate_url
from politikdesk.political_memory import shift_store
from politikdesk.web.search import _escape_like
from politikdesk.web.ui.components import esc, esc_attr, esc_url

client = TestClient(app)


# =============================================================================
# 1. SSRF ADVERSARIAL SECOND PASS MATRIX
# =============================================================================


@pytest.mark.parametrize(
    "url,reason",
    [
        # IPv4 Loopback
        ("http://127.0.0.1/status", "IPv4 loopback standard"),
        ("http://127.0.0.2/admin", "IPv4 loopback secondary"),
        ("http://127.255.255.254/metrics", "IPv4 loopback subnet edge"),
        ("http://0.0.0.0:8000/", "IPv4 unspecified"),
        # RFC 1918 Private
        ("http://10.0.0.1:8080/internal", "RFC1918 Class A"),
        ("http://172.16.0.1/secret", "RFC1918 Class B"),
        ("http://192.168.1.1/config", "RFC1918 Class C"),
        # Link-local & Cloud Metadata
        ("http://169.254.169.254/latest/meta-data/", "AWS/GCP/Azure IMDS metadata"),
        ("http://169.254.0.1/link", "IPv4 link-local"),
        # RFC 6598 CGNAT
        ("http://100.64.0.1/cgnat", "RFC6598 CGNAT low"),
        ("http://100.100.100.100/cgnat", "RFC6598 CGNAT mid"),
        ("http://100.127.255.254/cgnat", "RFC6598 CGNAT high"),
        # TEST-NET & Benchmarking & Multicast & Reserved
        ("http://192.0.2.1/test", "TEST-NET-1"),
        ("http://198.51.100.1/test", "TEST-NET-2"),
        ("http://203.0.113.1/test", "TEST-NET-3"),
        ("http://198.18.0.1/benchmark", "Benchmark network"),
        ("http://224.0.0.1/multicast", "IPv4 multicast"),
        ("http://240.0.0.1/reserved", "IPv4 reserved Class E"),
        ("http://255.255.255.255/broadcast", "IPv4 broadcast"),
        # IPv6 Loopback, ULA, Link-local, Multicast, Doc
        ("http://[::1]/admin", "IPv6 loopback"),
        ("http://[::]/admin", "IPv6 unspecified"),
        ("http://[fc00::1]/admin", "IPv6 ULA"),
        ("http://[fe80::1]/admin", "IPv6 link-local"),
        ("http://[ff02::1]/admin", "IPv6 multicast"),
        ("http://[2001:db8::1]/admin", "IPv6 doc"),
        # IPv4-Mapped IPv6
        ("http://[::ffff:127.0.0.1]/status", "IPv4-mapped IPv6 loopback"),
        ("http://[::ffff:10.0.0.1]/admin", "IPv4-mapped IPv6 private"),
        ("http://[::ffff:169.254.169.254]/meta", "IPv4-mapped IPv6 metadata"),
        ("http://[::ffff:100.64.0.1]/cgnat", "IPv4-mapped IPv6 CGNAT"),
        # Alternative Representations (Hex, Octal, Decimal Integers, Dotted)
        ("http://2130706433/internal", "Decimal integer 127.0.0.1"),
        ("http://0x7f000001/internal", "Hex integer 127.0.0.1"),
        ("http://0x7f.0.0.1/internal", "Dotted hex 127.0.0.1"),
        ("http://0177.0.0.1/internal", "Dotted octal 127.0.0.1"),
        ("http://017700000001/internal", "Octal integer 127.0.0.1"),
        # Hostnames
        ("http://localhost:8000/api", "localhost hostname"),
        ("http://localhost./api", "localhost trailing dot"),
        ("http://server.local/api", ".local suffix"),
        ("http://db.internal/api", ".internal suffix"),
        ("http://node.corp/api", ".corp suffix"),
        ("http://gateway.lan/api", ".lan suffix"),
        # Non-HTTP Schemes
        ("file:///etc/passwd", "file scheme"),
        ("gopher://127.0.0.1:70/", "gopher scheme"),
        ("ftp://127.0.0.1/data", "ftp scheme"),
        ("javascript:alert(1)", "javascript scheme"),
        ("data:text/html,payload", "data scheme"),
        ("ws://127.0.0.1:8000/socket", "ws scheme"),
        ("wss://127.0.0.1:8000/socket", "wss scheme"),
    ],
)
def test_adversarial_ssrf_all_vectors_blocked(url: str, reason: str) -> None:
    """Tüm SSRF varyantları (IP, hex, octal, mapping, scheme) kesinlikle reddedilmelidir."""
    with pytest.raises(UnsafeUrlError):
        validate_url(url, resolve_dns=False)


def test_ssrf_valid_public_urls_allowed() -> None:
    """Meşru internet adresleri ve genel IP'ler kabul edilmelidir."""
    assert (
        validate_url("https://evds2.tcmb.gov.tr/service", resolve_dns=False)
        == "https://evds2.tcmb.gov.tr/service"
    )
    assert (
        validate_url("https://8.8.8.8/dns-query", resolve_dns=False) == "https://8.8.8.8/dns-query"
    )
    assert (
        validate_url("https://1.1.1.1/dns-query", resolve_dns=False) == "https://1.1.1.1/dns-query"
    )


def test_http_client_event_hook_enforces_ssrf_on_all_requests() -> None:
    """HttpClient istek kancası (request hook) her istekte SSRF denetimi yapmalıdır."""
    client_inst = HttpClient(enforce_ssrf=True, resolve_dns=False)
    with pytest.raises(UnsafeUrlError):
        client_inst.get("http://127.0.0.1:8000/internal")
    client_inst.close()


# =============================================================================
# 2. AUTH + CSRF STATE-CHANGING ENDPOINT MATRIX
# =============================================================================


def test_auth_token_exact_status_code_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kimlik doğrulama matrisi kesin HTTP durum kodları ile doğrulanmalıdır."""
    secret_token = "pd_live_sec_" + secrets.token_hex(16)
    monkeypatch.setattr(get_settings(), "api_token", secret_token)

    # 1. No token -> 401 Unauthorized
    resp_no_token = client.get("/api/stance/diff")
    assert resp_no_token.status_code == 401
    assert "Kimlik doğrulama gerekli" in resp_no_token.json()["detail"]

    # 2. Empty token -> 401
    resp_empty = client.get("/api/stance/diff", headers={"Authorization": "Bearer "})
    assert resp_empty.status_code == 401

    # 3. Whitespace token -> 401
    resp_ws = client.get("/api/stance/diff", headers={"Authorization": "Bearer    "})
    assert resp_ws.status_code == 401

    # 4. Malformed Bearer header -> 401
    resp_malformed = client.get("/api/stance/diff", headers={"Authorization": "Token abcdef"})
    assert resp_malformed.status_code == 401

    # 5. Wrong token -> 403 Forbidden
    resp_wrong = client.get("/api/stance/diff", headers={"Authorization": "Bearer wrong_token_val"})
    assert resp_wrong.status_code == 403
    assert "Geçersiz belirteç" in resp_wrong.json()["detail"]

    # 6. Correct Bearer token -> 200 OK
    resp_ok = client.get("/api/stance/diff", headers={"Authorization": f"Bearer {secret_token}"})
    assert resp_ok.status_code == 200

    # 7. Correct X-API-Token -> 200 OK
    resp_x_token = client.get("/api/stance/diff", headers={"X-API-Token": secret_token})
    assert resp_x_token.status_code == 200

    # 8. Exempt paths -> 200 OK without token
    assert client.get("/health/live").status_code == 200
    assert client.get("/version").status_code == 200


def test_csrf_state_changing_methods_matrix() -> None:
    """CSRF koruması durum değiştiren (POST, PUT, DELETE) tüm metotlarda kesin olarak doğrulanmalıdır."""
    # 1. POST with cross-origin mismatch -> 403 Forbidden
    resp_post_cross = client.post(
        "/admin/events/1/status",
        data={"status": "archived"},
        headers={"Origin": "https://attacker.evil.com", "Host": "politikdesk.local"},
    )
    assert resp_post_cross.status_code == 403
    assert "CSRF" in resp_post_cross.json()["detail"]

    # 2. PUT with cross-origin mismatch -> 403 Forbidden
    resp_put_cross = client.put(
        "/admin/events/1",
        headers={"Origin": "https://attacker.evil.com", "Host": "politikdesk.local"},
    )
    assert resp_put_cross.status_code == 403

    # 3. DELETE with cross-origin mismatch -> 403 Forbidden
    resp_del_cross = client.delete(
        "/admin/events/1",
        headers={"Origin": "https://attacker.evil.com", "Host": "politikdesk.local"},
    )
    assert resp_del_cross.status_code == 403

    # 4. POST on UI route without Origin/Referer -> 403 Forbidden
    resp_no_origin = client.post(
        "/admin/events/1/status",
        data={"status": "archived"},
        headers={"Host": "politikdesk.local"},
    )
    assert resp_no_origin.status_code == 403

    # 5. POST with matching Origin -> Passes CSRF
    resp_same_origin = client.post(
        "/admin/events/999999/status",
        data={"status": "archived"},
        headers={"Origin": "http://politikdesk.local", "Host": "politikdesk.local"},
    )
    # CSRF passed; route handler executes (returns 404 or redirect, but NOT 403 CSRF)
    assert resp_same_origin.status_code != 403

    # 6. GET on programmatic API route without Origin -> Allowed for API clients
    resp_api = client.get("/api/search", params={"q": "tcmb"})
    assert resp_api.status_code == 200


# =============================================================================
# 3. CSP NONCE & XSS SANITIZATION
# =============================================================================


def test_csp_nonce_rotation_and_entropy() -> None:
    """CSP nonce'u her istekte yenilenmeli ve yeterli entropiye (>=16 bayt) sahip olmalıdır."""
    r1 = client.get("/")
    r2 = client.get("/")

    csp1 = r1.headers.get("Content-Security-Policy", "")
    csp2 = r2.headers.get("Content-Security-Policy", "")

    assert "nonce-" in csp1
    assert "nonce-" in csp2
    assert "script-src 'self' 'nonce-" in csp1
    assert "'unsafe-inline'" not in csp1.split("script-src")[1].split(";")[0]
    assert "'unsafe-eval'" not in csp1
    assert "object-src 'none'" in csp1
    assert "frame-ancestors 'self'" in csp1

    # Nonce extraction
    n1 = csp1.split("'nonce-")[1].split("'")[0]
    n2 = csp2.split("'nonce-")[1].split("'")[0]

    assert n1 != n2, "Nonce iki ardışık istek arasında değişmedi!"
    assert len(n1) >= 20, f"Nonce entropisi yetersiz: {len(n1)} karakter"

    # HTML içerisindeki script nonce ile CSP başlığındaki nonce birebir eşleşmeli
    if "<script nonce=" in r1.text:
        html_nonce = r1.text.split('<script nonce="')[1].split('"')[0]
        assert html_nonce == n1, "HTML script nonce ile CSP başlık nonce'u eşleşmiyor!"


def test_xss_sanitization_neutralizes_all_adversarial_vectors() -> None:
    """esc(), esc_url() ve esc_attr() tüm XSS ve enjeksiyon vektörlerini nötralize etmelidir."""
    # 1. URL Protocol Injection
    assert esc_url("javascript:alert(1)") == "#"
    assert esc_url("JAVASCRIPT:alert(1)") == "#"
    assert esc_url("vbscript:msgbox(1)") == "#"
    assert esc_url("data:text/html,<script>alert(1)</script>") == "#"
    assert esc_url("   javascript:alert(1)") == "#"
    assert esc_url("javascript\n:alert(1)") == "#"
    assert esc_url("https://tcmb.gov.tr") == "https://tcmb.gov.tr"

    # 2. HTML escaping
    assert "&lt;script&gt;" in esc("<script>alert(1)</script>")
    assert "&quot;" in esc('"test"')
    assert "&#x27;" in esc("'test'")

    # 3. Attribute escaping
    assert "&quot;&gt;&lt;script&gt;" in esc_attr('"><script>alert(1)</script>')
    assert "&#x27;" in esc_attr("x' onmouseover='alert(1)")


# =============================================================================
# 4. SQL INJECTION & LIKE WILDCARD ESCAPING
# =============================================================================


def test_sql_like_wildcard_escaping_comprehensive() -> None:
    """_escape_like fonksiyonu %, _ ve \\ karakterlerini tam olarak kaçırmalıdır."""
    assert _escape_like("plain") == "plain"
    assert _escape_like("100%") == "100\\%"
    assert _escape_like("user_name") == "user\\_name"
    assert _escape_like("C:\\Windows") == "C:\\\\Windows"
    assert _escape_like("%_%\\") == "\\%\\_\\%\\\\"
    assert _escape_like("%%50%%_test_") == "\\%\\%50\\%\\%\\_test\\_"


# =============================================================================
# 5. EVIDENCE ENGINE & AST ARCHITECTURE GUARD FALSIFICATION
# =============================================================================


def test_ast_architecture_guard_adversarial_falsification(tmp_path: Path) -> None:
    """AST mimari koruyucu, evidence/ altına LLM importu sızarsa fail-closed olmalıdır."""
    from scripts.check_architecture import RULES, check

    evidence_rule = next(r for r in RULES if r.package == "politikdesk/evidence")

    # 1. Clean synthetic directory -> 0 violations
    clean_dir = tmp_path / "politikdesk" / "evidence"
    clean_dir.mkdir(parents=True)
    (clean_dir / "__init__.py").write_text("", encoding="utf-8")
    (clean_dir / "clean_module.py").write_text(
        "from politikdesk.db import connection\n\ndef run():\n    return 42\n",
        encoding="utf-8",
    )
    violations_clean = check(tmp_path, (evidence_rule,))
    assert violations_clean == [], "Temiz modülde ihlal bulundu!"

    # 2. Adversarial direct import injection -> Must catch violation
    (clean_dir / "violator.py").write_text(
        "from politikdesk.llm.client import LLMClient\n",
        encoding="utf-8",
    )
    violations_caught = check(tmp_path, (evidence_rule,))
    assert len(violations_caught) == 1
    assert violations_caught[0].imported == "politikdesk.llm.client"

    # 3. Adversarial dynamic import injection -> Must catch violation
    (clean_dir / "violator.py").write_text(
        'import importlib\nmod = importlib.import_module("politikdesk.llm.client")\n',
        encoding="utf-8",
    )
    violations_dynamic = check(tmp_path, (evidence_rule,))
    assert len(violations_dynamic) >= 1

    # 4. Cleanup and verify clean state
    (clean_dir / "violator.py").unlink()
    assert check(tmp_path, (evidence_rule,)) == []


# =============================================================================
# 6. EPISTEMIC SAFETY (ADR-010 & PUBLISH_GATE_OPEN)
# =============================================================================


def test_epistemic_safety_publish_gate_closed_by_default() -> None:
    """ADR-010 uyarınca PUBLISH_GATE_OPEN kesinlikle False olmalıdır."""
    assert shift_store.PUBLISH_GATE_OPEN is False
    assert shift_store.list_all() == []
    assert shift_store.for_actor("Ahmet Yılmaz") == []
    assert shift_store.for_event(101) == []
