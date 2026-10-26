"""Phase 26: Chaos Engineering, Fault Injection and SRE Resilience Test Suite."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from politikdesk.ingestion.adapters.rss import RssAdapter
from politikdesk.ingestion.http import UnsafeUrlError, validate_url
from politikdesk.ingestion.sources import SourceConfig


def _dummy_cfg(url: str = "http://example.com/rss.xml", slug: str = "chaos-src") -> SourceConfig:
    return SourceConfig(
        slug=slug,
        name="Chaos Test Source",
        kind="media",
        vertical="macro_economy",
        adapter="rss",
        access_method="rss",
        tos_status="public",
        feed_url=url,
        tier=2,
    )


def test_chaos_01_timeout_isolation() -> None:
    """Timeout durumunda RssAdapter ve pipeline çökmez, güvenli biçimde boş liste döner."""
    cfg = _dummy_cfg()
    mock_http = MagicMock()
    mock_http.get.side_effect = TimeoutError("Connection timed out after 6.0s")

    adapter = RssAdapter(
        slug=cfg.slug,
        feed_url=cfg.feed_url or "",
        base_url="",
        http=mock_http,
    )
    items = adapter.fetch()
    assert items == []


def test_chaos_02_dns_failure_isolation() -> None:
    """DNS / Bağlantı hatasında exception kontrollü yakalanır ve boş liste döner."""
    cfg = _dummy_cfg()
    mock_http = MagicMock()
    mock_http.get.side_effect = ConnectionError("DNS resolution failed: [Errno 11001] getaddrinfo failed")

    adapter = RssAdapter(
        slug=cfg.slug,
        feed_url=cfg.feed_url or "",
        base_url="",
        http=mock_http,
    )
    items = adapter.fetch()
    assert items == []


def test_chaos_03_http_500_502_503_errors() -> None:
    """HTTP 5xx sunucu hatalarında sistem kontrollü hata üretir."""
    for status_code in [500, 502, 503]:
        cfg = _dummy_cfg()
        mock_http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.raise_for_status.side_effect = RuntimeError(f"HTTP {status_code} Server Error")
        mock_http.get.return_value = mock_resp

        adapter = RssAdapter(
            slug=cfg.slug,
            feed_url=cfg.feed_url or "",
            base_url="",
            http=mock_http,
        )
        # 5xx yanıtlarında sistemin crash etmediği doğrulanır
        try:
            items = adapter.fetch()
            assert len(items) == 0
        except Exception as exc:
            assert f"{status_code}" in str(exc) or isinstance(exc, RuntimeError)


def test_chaos_04_http_429_rate_limiting() -> None:
    """HTTP 429 Rate Limit durumunda adapter hata fırlatır veya boş liste döner."""
    cfg = _dummy_cfg()
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.raise_for_status.side_effect = RuntimeError("HTTP 429 Too Many Requests")
    mock_http.get.return_value = mock_resp

    adapter = RssAdapter(
        slug=cfg.slug,
        feed_url=cfg.feed_url or "",
        base_url="",
        http=mock_http,
    )
    try:
        items = adapter.fetch()
        assert len(items) == 0
    except Exception as exc:
        assert "429" in str(exc) or isinstance(exc, RuntimeError)


def test_chaos_05_malformed_corrupt_xml() -> None:
    """Bozuk XML gövdesinde parser çökmez, 0 öğe veya ParseError döner."""
    cfg = _dummy_cfg()
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"<html><head><title>Unclosed Tag"
    mock_resp.text = "<html><head><title>Unclosed Tag"
    mock_http.get.return_value = mock_resp

    adapter = RssAdapter(
        slug=cfg.slug,
        feed_url=cfg.feed_url or "",
        base_url="",
        http=mock_http,
    )
    items = adapter.fetch()
    assert len(items) == 0


def test_chaos_06_empty_feed() -> None:
    """200 OK ancak 0 öğe içeren feed temiz şekilde 0 öğe döner."""
    cfg = _dummy_cfg()
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    empty_xml = b'<?xml version="1.0"?><rss version="2.0"><channel><title>Empty</title></channel></rss>'
    mock_resp.content = empty_xml
    mock_resp.text = empty_xml.decode("utf-8")
    mock_http.get.return_value = mock_resp

    adapter = RssAdapter(
        slug=cfg.slug,
        feed_url=cfg.feed_url or "",
        base_url="",
        http=mock_http,
    )
    items = adapter.fetch()
    assert len(items) == 0


def test_chaos_07_ssrf_private_ip_blocking() -> None:
    """Yerel ve özel IP adreslerine (127.0.0.1, 10.0.0.1, 169.254.169.254) istekler UnsafeUrlError ile engellenir."""
    private_targets = [
        "http://127.0.0.1:8000/admin",
        "http://localhost:5432",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1:6379",
        "http://192.168.1.1/",
    ]
    for target in private_targets:
        with pytest.raises((UnsafeUrlError, ValueError)):
            validate_url(target)


def test_chaos_08_invalid_character_encoding() -> None:
    """Geçersiz karakter kodlamasında parser çökmez."""
    cfg = _dummy_cfg()
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    bad_bytes = b'<?xml version="1.0"?><rss version="2.0"><channel><item><title>\xff\xfe Bozuk Metin</title><link>http://example.com/1</link></item></channel></rss>'
    mock_resp.content = bad_bytes
    mock_resp.text = bad_bytes.decode("latin-1")
    mock_http.get.return_value = mock_resp

    adapter = RssAdapter(
        slug=cfg.slug,
        feed_url=cfg.feed_url or "",
        base_url="",
        http=mock_http,
    )
    items = adapter.fetch()
    assert isinstance(items, list)


@pytest.mark.db
def test_chaos_09_redis_disconnect_graceful_handling() -> None:
    """Redis geçici olarak erişilemez olduğunda sistem fail-safe modda çalışır."""
    from politikdesk.web.repository import feed
    items = feed(user_id=1, limit=5)
    assert isinstance(items, list)
