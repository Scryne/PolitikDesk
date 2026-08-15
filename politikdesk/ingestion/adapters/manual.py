"""Kullanıcı-tetikli manuel içe aktarma (F1-04).

DoD: Bir X gönderi linki veya haber linki yapıştırıldığında Tier 4/3
`article` kaydı oluşuyor.

Spec §9.4 / D7: X API **kullanılmaz**. Gönderi linki yapıştırıldığında
yalnızca genel meta veri (oEmbed / Open Graph) okunur — bu, API değil
kamuya açık sayfa meta verisidir.

⚠️ Güvenlik: kullanıcıdan gelen URL doğrudan çekilir. SSRF'ye karşı
`validate_url()` iç ağ adreslerini reddeder (F4-09'un erken uygulaması —
kullanıcı girdisi alan ilk uç burasıdır, korumasız bırakılamaz).
"""

from __future__ import annotations

import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from politikdesk.ingestion.http import HttpClient
from politikdesk.ingestion.models import RawItem
from politikdesk.observability import get_logger

log = get_logger(__name__)

# Sosyal platformlar Tier 4'e düşer (Spec §9.1); R7 gereği asla 🟢 olamaz.
SOCIAL_HOSTS = frozenset({
    "x.com", "twitter.com", "mobile.twitter.com", "nitter.net",
    "bsky.app", "threads.net", "mastodon.social",
})

_ALLOWED_SCHEMES = frozenset({"http", "https"})


class UnsafeUrlError(ValueError):
    """URL güvenli değil (iç ağ, desteklenmeyen şema, çözülemeyen host)."""


MAX_REDIRECTS = 3


def validate_url(url: str, *, resolve_dns: bool = True) -> str:
    """SSRF koruması: yalnızca genel internet adreslerine izin verir."""
    parsed = urlparse(url.strip())

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"Desteklenmeyen şema: {parsed.scheme!r}")
    if not parsed.hostname:
        raise UnsafeUrlError("URL'de host yok")

    host = parsed.hostname.lower().strip("[]")
    if (
        host in {"localhost", "localhost.localdomain", "0.0.0.0", "127.0.0.1", "::1"}
        or host.endswith(".local")
        or host.endswith(".internal")
        or host.endswith(".corp")
        or host.endswith(".lan")
    ):
        raise UnsafeUrlError(f"Yerel/özel adrese erişilemez: {host}")

    # Doğrudan IP verilmişse
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None

    if ip is not None and _is_private(ip):
        raise UnsafeUrlError(f"Özel/ayrılmış IP adresine erişilemez: {host}")

    if resolve_dns and ip is None:
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror as exc:
            raise UnsafeUrlError(f"Host çözümlenemedi: {host}") from exc
        for info in infos:
            resolved = ipaddress.ip_address(info[4][0])
            if _is_private(resolved):
                raise UnsafeUrlError(
                    f"Host özel bir adrese çözümleniyor: {host} -> {resolved}"
                )

    return url.strip()


def _is_private(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


class _MetaParser(HTMLParser):
    """Open Graph / Twitter Card meta etiketlerini ve <title>'ı toplar."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title: str = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
            return
        if tag != "meta":
            return
        data = {k.lower(): (v or "") for k, v in attrs}
        key = data.get("property") or data.get("name")
        content = data.get("content")
        if key and content:
            self.meta[key.lower()] = content

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and not self.title:
            self.title = data.strip()


def parse_metadata(html: str) -> dict[str, str]:
    parser = _MetaParser()
    parser.feed(html)
    meta = parser.meta

    return {
        "title": (
            meta.get("og:title") or meta.get("twitter:title") or parser.title or ""
        ).strip(),
        "description": (
            meta.get("og:description") or meta.get("twitter:description")
            or meta.get("description") or ""
        ).strip(),
        "published_at": (
            meta.get("article:published_time") or meta.get("og:updated_time") or ""
        ).strip(),
        "site_name": meta.get("og:site_name", "").strip(),
    }


class ManualImportAdapter:
    """Tek bir URL'den meta veri okuyup RawItem üretir (F1-04)."""

    slug = "manual"

    def __init__(self, http: HttpClient | None = None) -> None:
        # Manuel içe aktarma kullanıcı tetiklidir; robots.txt bir tarama
        # kısıtıdır ve tek seferlik kullanıcı isteğine uygulanmaz.
        self.http = http or HttpClient(respect_robots=False, max_per_minute=30)

    def fetch_one(self, url: str, *, source_slug: str | None = None) -> RawItem:
        from politikdesk.ingestion.adapters.rss import parse_feed_date

        current_url = validate_url(url)
        visited_urls: set[str] = {current_url}
        response = None

        # Güvenli adım-adım yönlendirme doğrulaması (SSRF bypass savunması)
        for _ in range(MAX_REDIRECTS + 1):
            response = self.http.get(
                current_url, source_slug="manual", follow_redirects=False
            )
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                if not location:
                    break
                next_url = urljoin(current_url, location)
                safe_next_url = validate_url(next_url)
                if safe_next_url in visited_urls:
                    raise UnsafeUrlError(f"Yönlendirme döngüsü tespit edildi: {next_url}")
                visited_urls.add(safe_next_url)
                current_url = safe_next_url
            else:
                break
        else:
            raise UnsafeUrlError(f"Çok fazla yönlendirme (azami {MAX_REDIRECTS}): {url}")

        if response.status_code >= 400:
            response.raise_for_status()

        meta = parse_metadata(response.text)

        title = meta["title"] or _fallback_title(current_url)
        published = parse_feed_date(meta["published_at"]) if meta["published_at"] else None

        return RawItem(
            source_slug=source_slug or classify_host(current_url),
            url=current_url,
            title=title,
            published_at=published,
            summary=meta["description"] or None,
            guid=current_url,
            extra={"manual_import": True, "site_name": meta["site_name"]},
        )

    def fetch(self) -> list[RawItem]:
        """Protokol uyumu için. Manuel adaptör toplu çekim yapmaz."""
        return []


def classify_host(url: str) -> str:
    """URL'in hangi kaynak slug'ına ait olduğunu tahmin eder."""
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if host in SOCIAL_HOSTS:
        return "manual-social"
    return "manual-web"


def is_social(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return host in SOCIAL_HOSTS


def _fallback_title(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    tail = path.rsplit("/", 1)[-1] if path else ""
    cleaned = tail.replace("-", " ").replace("_", " ").strip()
    return cleaned[:200] or url[:200]
