"""Faz 24: Ingestion Pipeline Hata Simülasyonu ve Dayanıklılık Test Süiti.

Simüle edilen senaryolar:
1. Timeout (Bağlantı zaman aşımı)
2. DNS Failure (Geçersiz sunucu adı)
3. HTTP 500 Internal Server Error
4. HTTP 429 Too Many Requests (Rate Limiting)
5. Malformed RSS (Bozuk XML / Parse Hatası)
6. Empty RSS (200 OK ama 0 öğe)
7. Redirects / Multiple Feeds
8. Partial Failure in Multi-feed Sources
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from politikdesk.ingestion.adapters.rss import RssAdapter


@dataclass
class FakeResponse:
    content: bytes
    status_code: int = 200
    headers: dict[str, str] | None = None

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


class FakeHttpClient:
    def __init__(self, handler_or_response: Any) -> None:
        self.handler = handler_or_response

    def get(self, url: str, headers: dict[str, str] | None = None, **_: Any) -> FakeResponse:
        if callable(self.handler):
            return self.handler(url, headers)
        if isinstance(self.handler, Exception):
            raise self.handler
        return self.handler

    def close(self) -> None:
        pass


def test_scenario_timeout_resilience() -> None:
    """Senaryo 1: Zaman aşımına uğrayan kaynak pipeline'ı çökertmemeli, boş liste dönüp hata kaydetmeli."""
    client = FakeHttpClient(httpx.TimeoutException("Connection timed out"))
    adapter = RssAdapter("timeout-src", "https://example.com/feed.xml", http=client)  # type: ignore[arg-type]

    items = adapter.fetch()
    assert items == []
    failures = adapter.drain_failures()
    assert len(failures) == 1
    assert "timeoutexception" in failures[0].lower()


def test_scenario_dns_failure_resilience() -> None:
    """Senaryo 2: DNS çözümlenemeyen kaynak güvenle izole edilmeli."""
    client = FakeHttpClient(httpx.ConnectError("Failed to resolve host"))
    adapter = RssAdapter(
        "dns-fail-src", "https://invalid-non-existent-domain.xyz/feed.xml", http=client
    )  # type: ignore[arg-type]

    items = adapter.fetch()
    assert items == []
    failures = adapter.drain_failures()
    assert len(failures) == 1
    assert "connecterror" in failures[0].lower()


def test_scenario_http_500_server_error() -> None:
    """Senaryo 3: 500 hatası fırlatan kaynak failure kaydetmeli."""
    client = FakeHttpClient(
        httpx.HTTPStatusError(
            "500 Server Error",
            request=httpx.Request("GET", "https://example.com"),
            response=httpx.Response(500),
        )
    )
    adapter = RssAdapter("500-src", "https://example.com/feed.xml", http=client)  # type: ignore[arg-type]

    items = adapter.fetch()
    assert items == []
    failures = adapter.drain_failures()
    assert len(failures) == 1
    assert "httpstatuserror" in failures[0].lower()


def test_scenario_http_429_rate_limit() -> None:
    """Senaryo 4: 429 Too Many Requests hatası izole edilmeli."""
    client = FakeHttpClient(
        httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=httpx.Request("GET", "https://example.com"),
            response=httpx.Response(429),
        )
    )
    adapter = RssAdapter("429-src", "https://example.com/feed.xml", http=client)  # type: ignore[arg-type]

    items = adapter.fetch()
    assert items == []
    failures = adapter.drain_failures()
    assert len(failures) == 1
    assert "httpstatuserror" in failures[0].lower()


def test_scenario_malformed_xml_rss() -> None:
    """Senaryo 5: Bozuk veya eksik kapatılmış XML dosyasında çökmek yerine hata yakalanmalı."""
    malformed_content = b"""<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>Bozuk Akis</title>
        <item>
          <title>Baslik Kapanmadi
        </item>
      </channel>
    """  # </rss> eksik

    client = FakeHttpClient(FakeResponse(content=malformed_content, status_code=200))
    adapter = RssAdapter("malformed-src", "https://example.com/feed.xml", http=client)  # type: ignore[arg-type]

    items = adapter.fetch()
    assert items == []
    failures = adapter.drain_failures()
    assert len(failures) == 1
    assert "malformedfeed" in failures[0].lower() or "xml" in failures[0].lower()


def test_scenario_empty_rss_feed() -> None:
    """Senaryo 6: Geçerli XML ama 0 item içeren boş feed güvenle 0 öğe dönmeli ve uyarılmalı."""
    empty_rss = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Bos Akis</title>
        <link>https://example.com</link>
        <description>Hic haber yok</description>
      </channel>
    </rss>
    """

    client = FakeHttpClient(FakeResponse(content=empty_rss, status_code=200))
    adapter = RssAdapter("empty-src", "https://example.com/feed.xml", http=client)  # type: ignore[arg-type]

    items = adapter.fetch()
    assert items == []
    failures = adapter.drain_failures()
    assert len(failures) == 1
    assert (
        "malformedfeed" in failures[0].lower()
        or "öğe" in failures[0].lower()
        or "entry" in failures[0].lower()
        or "item" in failures[0].lower()
    )


def test_scenario_valid_feed_item_extraction() -> None:
    """Senaryo 7: Düzgün RSS akışından öğeler başarıyla çekilmeli."""
    valid_rss = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Gecerli Akis</title>
        <link>https://example.com</link>
        <item>
          <title>Merkez Bankasi Faiz Karari</title>
          <link>https://example.com/haber-1</link>
          <description>PPK faiz oranini acikladi.</description>
          <pubDate>Mon, 24 Aug 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """

    client = FakeHttpClient(FakeResponse(content=valid_rss, status_code=200))
    adapter = RssAdapter("valid-src", "https://example.com/feed.xml", http=client)  # type: ignore[arg-type]

    items = adapter.fetch()
    assert len(items) == 1
    assert items[0].title == "Merkez Bankasi Faiz Karari"
    assert items[0].url == "https://example.com/haber-1"
    assert len(adapter.drain_failures()) == 0


def test_scenario_multiple_feeds_one_fails_others_succeed() -> None:
    """Senaryo 8: Birden çok feed url'si olan bir kaynakta bir URL çökse bile diğerleri çalışmaya devam etmeli."""
    valid_rss = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Calisan Akis</title>
        <item>
          <title>Saglam Feed Haberi</title>
          <link>https://example.com/haber-2</link>
        </item>
      </channel>
    </rss>
    """

    def multi_handler(url: str, _headers: dict[str, str] | None) -> FakeResponse:
        if "broken" in url:
            raise httpx.ConnectError("Broken feed connection error")
        return FakeResponse(content=valid_rss, status_code=200)

    client = FakeHttpClient(multi_handler)
    adapter = RssAdapter(
        "multi-src",
        "https://example.com/broken-feed.xml",
        extra_feeds=["https://example.com/working-feed.xml"],
        http=client,  # type: ignore[arg-type]
    )

    items = adapter.fetch()
    assert len(items) == 1
    assert items[0].title == "Saglam Feed Haberi"
    assert len(adapter.drain_failures()) == 1
