"""RSS / Atom adaptörü (F1-02).

DoD: Tier 2–3 kaynaklardan başlık/link/tarih çekiliyor; hatalı feed'de
çökmüyor, loglayıp geçiyor.

Bağımlılık notu: `feedparser` yerine stdlib `xml.etree` kullanılıyor.
Gerekçe: RSS 2.0 ve Atom'un ihtiyaç duyduğumuz alt kümesi küçük ve
kararlı; ek bir bağımlılık, ayrıştırma hatalarını bizim kontrolümüzden
çıkarır ve kaynak başına davranışı özelleştirmeyi zorlaştırır.
"""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin
from xml.etree import ElementTree

from politikdesk.ingestion.adapters.base import FailureRecorder, registry
from politikdesk.ingestion.http import HttpClient
from politikdesk.ingestion.models import RawItem
from politikdesk.observability import get_logger

log = get_logger(__name__)

ATOM_NS = "{http://www.w3.org/2005/Atom}"

# Bazı kaynaklar tarih alanını farklı isimlendirir.
_DATE_TAGS = (
    "pubDate",
    "published",
    "updated",
    f"{ATOM_NS}published",
    f"{ATOM_NS}updated",
    "{http://purl.org/dc/elements/1.1/}date",
)


class RssAdapter(FailureRecorder):
    """Bir veya birden çok RSS/Atom akışından öğe çeker."""

    def __init__(
        self,
        slug: str,
        feed_url: str,
        *,
        base_url: str = "",
        extra_feeds: list[str] | None = None,
        http: HttpClient | None = None,
        keyword_filter: list[str] | None = None,
        max_items: int = 100,
    ) -> None:
        super().__init__()
        self.slug = slug
        self.feed_urls = [feed_url, *(extra_feeds or [])]
        self.base_url = base_url
        self.http = http or HttpClient()
        self.keyword_filter = [k.casefold() for k in (keyword_filter or [])]
        self.max_items = max_items

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        for feed_url in self.feed_urls:
            try:
                items.extend(self._fetch_one(feed_url))
            except Exception as exc:  # noqa: BLE001 — bir akış diğerlerini düşürmez
                self.record_failure(feed_url, exc)
                log.warning(
                    "rss_feed_failed",
                    source=self.slug,
                    feed_url=feed_url,
                    error=type(exc).__name__,
                    detail=str(exc)[:200],
                )
        return items[: self.max_items]

    # ------------------------------------------------------------------
    def _fetch_one(self, feed_url: str) -> list[RawItem]:
        response = self.http.get(feed_url, source_slug=self.slug)
        return self.parse(response.text, feed_url=feed_url)

    def parse(self, xml_text: str, *, feed_url: str = "") -> list[RawItem]:
        """XML metnini RawItem listesine çevirir. Ağ erişimi gerektirmez."""
        try:
            root = ElementTree.fromstring(xml_text.strip())
        except ElementTree.ParseError as exc:
            raise MalformedFeed(f"{feed_url}: XML ayrıştırılamadı — {exc}") from exc

        entries = root.findall(".//item") or root.findall(f".//{ATOM_NS}entry")
        if not entries:
            raise MalformedFeed(f"{feed_url}: akışta <item>/<entry> yok")

        items: list[RawItem] = []
        for entry in entries:
            item = self._parse_entry(entry)
            if item is None:
                continue
            if not self._passes_keyword_filter(item):
                continue
            items.append(item)
        return items

    def _parse_entry(self, entry: ElementTree.Element) -> RawItem | None:
        title = _text(entry, "title") or _text(entry, f"{ATOM_NS}title")
        link = self._extract_link(entry)

        if not title or not link:
            # Eksik alanlı öğe atlanır — tüm akışı düşürmez.
            return None

        return RawItem(
            source_slug=self.slug,
            url=link,
            title=" ".join(title.split()),
            published_at=self._extract_date(entry),
            summary=_text(entry, "description") or _text(entry, f"{ATOM_NS}summary"),
            guid=_text(entry, "guid") or _text(entry, f"{ATOM_NS}id"),
        )

    def _extract_link(self, entry: ElementTree.Element) -> str | None:
        raw = _text(entry, "link")
        if not raw:
            atom_link = entry.find(f"{ATOM_NS}link")
            if atom_link is not None:
                raw = atom_link.get("href")
        if not raw:
            return None
        raw = raw.strip()
        # TCMB gibi kaynaklar göreli yol döndürür.
        if raw.startswith("/") and self.base_url:
            return urljoin(self.base_url, raw)
        if not raw.startswith(("http://", "https://")):
            return urljoin(self.base_url, raw) if self.base_url else None
        return raw

    @staticmethod
    def _extract_date(entry: ElementTree.Element) -> datetime | None:
        for tag in _DATE_TAGS:
            raw = _text(entry, tag)
            if raw:
                parsed = parse_feed_date(raw)
                if parsed:
                    return parsed
        return None

    def _passes_keyword_filter(self, item: RawItem) -> bool:
        if not self.keyword_filter:
            return True
        haystack = f"{item.title} {item.summary or ''}".casefold()
        return any(keyword in haystack for keyword in self.keyword_filter)


class MalformedFeed(ValueError):
    """Akış ayrıştırılamadı."""


def _text(element: ElementTree.Element, tag: str) -> str | None:
    found = element.find(tag)
    if found is None or found.text is None:
        return None
    value = found.text.strip()
    return value or None


def parse_feed_date(raw: str) -> datetime | None:
    """RFC 2822 (RSS) ve ISO 8601 (Atom) tarihlerini UTC'ye çevirir."""
    raw = raw.strip()
    if not raw:
        return None

    try:
        parsed = parsedate_to_datetime(raw)
        return _to_utc(parsed)
    except (TypeError, ValueError):
        pass

    candidate = raw.replace("Z", "+00:00")
    try:
        return _to_utc(datetime.fromisoformat(candidate))
    except ValueError:
        return None


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        # Saat dilimi yoksa UTC varsayılır; Spec §9.3 tüm tarihler UTC.
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


registry.register("rss", RssAdapter)
