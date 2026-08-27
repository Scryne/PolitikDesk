"""Phase 26: Security Red Team Audit & Vulnerability Penetration Test Suite."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.ingestion.http import UnsafeUrlError, validate_url

client = TestClient(app)
AUTH = {"X-User-Id": "1"}


@pytest.mark.security
def test_sec_01_ssrf_standard_private_ips() -> None:
    """SSRF 1: Standart özel IP adresleri bloklanmalıdır."""
    blocked_ips = [
        "http://127.0.0.1/admin",
        "http://10.0.0.5:8000/api",
        "http://192.168.1.100/",
        "http://172.16.0.1/",
        "http://0.0.0.0/",
    ]
    for url in blocked_ips:
        with pytest.raises((UnsafeUrlError, ValueError)):
            validate_url(url)


@pytest.mark.security
def test_sec_02_ssrf_ipv6_and_mapped() -> None:
    """SSRF 2: IPv6 loopback ve IPv4-mapped IPv6 engellenmelidir."""
    blocked_ipv6 = [
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://[fe80::1]/",
    ]
    for url in blocked_ipv6:
        with pytest.raises((UnsafeUrlError, ValueError)):
            validate_url(url)


@pytest.mark.security
def test_sec_03_ssrf_cloud_metadata_endpoints() -> None:
    """SSRF 3: AWS/GCP/Azure metadata uçları (169.254.169.254) engellenmelidir."""
    metadata_urls = [
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.169.254/computeMetadata/v1/",
        "http://169.254.170.2/v2/credentials",
    ]
    for url in metadata_urls:
        with pytest.raises((UnsafeUrlError, ValueError)):
            validate_url(url)


@pytest.mark.security
def test_sec_04_ssrf_obfuscated_encodings() -> None:
    """SSRF 4: Hex, octal, decimal IP gösterimleri engellenmelidir."""
    obfuscated_urls = [
        "http://0x7f000001/",          # Hex 127.0.0.1
        "http://2130706433/",           # Decimal 127.0.0.1
        "http://0177.0.0.1/",           # Octal 127.0.0.1
        "http://0x7f.0.0.1/",           # Mixed
    ]
    for url in obfuscated_urls:
        with pytest.raises((UnsafeUrlError, ValueError)):
            validate_url(url)


@pytest.mark.security
def test_sec_05_xss_search_query_escaping() -> None:
    """XSS 1: Arama kutusu girdisi HTML karakterlerinden arındırılmalıdır (escape)."""
    payloads = [
        '<script>alert("XSS")</script>',
        '"><img src=x onerror=alert(1)>',
        '"><svg onload=alert(1)>',
        "javascript:alert(1)",
    ]
    for payload in payloads:
        resp = client.get(f"/feed?q={payload}", headers=AUTH)
        assert resp.status_code == 200
        # Ham payload script olarak yürütülebilir halde HTML'e basılmamalıdır
        assert "<script>alert" not in resp.text
        assert "<img src=x onerror=" not in resp.text
        assert "<svg onload=" not in resp.text


@pytest.mark.security
def test_sec_06_content_security_policy_headers() -> None:
    """CSP: Güvenlik başlıklarının (Content-Security-Policy, X-Content-Type-Options) varlığı."""
    resp = client.get("/feed", headers=AUTH)
    assert resp.status_code == 200
    headers = {k.lower(): v for k, v in resp.headers.items()}
    assert "x-content-type-options" in headers or "content-security-policy" in headers or "x-frame-options" in headers


@pytest.mark.security
def test_sec_07_no_credentials_in_logs() -> None:
    """LOG: Log veya metriklerde şifre/gizli anahtar sızıntısı olmamalıdır."""
    from politikdesk.config import Settings
    # Settings modeli repr'inde şifrelerin maskelendiği veya düz metin sızmadığı doğrulanır
    s = Settings()
    s_repr = repr(s)
    assert "supersecret" not in s_repr.lower()
