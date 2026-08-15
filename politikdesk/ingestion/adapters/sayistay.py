"""Sayıştay, Cumhurbaşkanlığı ve KİK Resmi Denetim Adaptörleri (S1/S2 · Spec v3.4 §5).

1. Sayıştay: Kamu kurumları ve belediye denetim raporları, usulsüzlük ve kamu zararı bulguları.
   "Hesap Sor" ve denetim katmanının en yüksek değerli girdisidir (Tier 1).
2. Cumhurbaşkanlığı Kararnameleri ve Resmi Duyuruları.
3. Kamu İhale Kurumu (KİK): İhale iptalleri ve uyuşmazlık kararları.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from html import unescape

from politikdesk.ingestion.adapters.base import FailureRecorder, registry
from politikdesk.ingestion.http import BROWSER_USER_AGENT, HttpClient
from politikdesk.ingestion.models import RawItem
from politikdesk.observability import get_logger

log = get_logger(__name__)

_TAGS = re.compile(r"<[^>]+>")
_ANCHOR = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)


def clean_text(raw: str) -> str:
    text = unescape(_TAGS.sub("", raw))
    return re.sub(r"\s+", " ", text).strip()


class SayistayAdapter(FailureRecorder):
    """Sayıştay Denetim Raporları toplayıcısı."""

    slug = "sayistay"

    def __init__(
        self,
        slug: str = "sayistay",
        *,
        base_url: str = "https://www.sayistay.gov.tr",
        http: HttpClient | None = None,
        keyword_filter: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.slug = slug
        self.base_url = base_url.rstrip("/")
        self.http = http or HttpClient(
            respect_robots=False,
            user_agent=BROWSER_USER_AGENT,
            timeout=30.0,
            max_retries=4,
        )
        self.keyword_filter = [k.casefold() for k in (keyword_filter or [])]

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()
        endpoints = [
            f"{self.base_url}/",
            f"{self.base_url}/pages/121-denetim-bulgulari",
        ]

        for url in endpoints:
            try:
                resp = self.http.get(url, source_slug=self.slug)
                for it in self._parse(resp.text, url):
                    if it.url not in seen:
                        seen.add(it.url)
                        items.append(it)
            except Exception as exc:  # noqa: BLE001
                self.record_failure(url, exc)
                log.warning("sayistay_fetch_failed", url=url, error=type(exc).__name__)

        return items

    def _parse(self, html: str, base_page_url: str) -> list[RawItem]:
        out: list[RawItem] = []
        now = datetime.now(UTC)

        # 1. Standart linkler
        for match in _ANCHOR.finditer(html):
            href, label = match.group(1), match.group(2)
            title = clean_text(label)
            if not title or len(title) < 10:
                continue

            keywords = (
                "rapor", "denetim", "bulgu", "düzenlilik",
                "kamu zararı", "sayıştay", "duyuru",
            )
            if any(k in title.casefold() for k in keywords):

                url = href if href.startswith("http") else f"{self.base_url}/{href.lstrip('/')}"
                out.append(
                    RawItem(
                        source_slug=self.slug,
                        url=url,
                        title=f"Sayıştay: {title}",
                        published_at=now,
                        summary=f"Sayıştay Başkanlığı Denetim ve Duyuru: {title}",
                        guid=url,
                        extra={"category": "denetim_ve_yolsuzluk", "vertical": "legislation"},
                    )
                )

        # 2. Duyuru onclick bağlantıları
        _DUYURU_ONCLICK = re.compile(
            r"onclick=\"location\.href='(/duyuru/\d+-[^']+)'\"",
            re.IGNORECASE,
        )
        for match in _DUYURU_ONCLICK.finditer(html):
            path = match.group(1)
            slug_part = path.split("/")[-1].replace("-", " ")
            url = f"{self.base_url}/{path.lstrip('/')}"
            out.append(
                RawItem(
                    source_slug=self.slug,
                    url=url,
                    title=f"Sayıştay Duyurusu: {slug_part.capitalize()}",
                    published_at=now,
                    summary=f"Sayıştay Başkanlığı Resmi Duyurusu: {slug_part}",
                    guid=url,
                    extra={"category": "denetim_ve_yolsuzluk", "vertical": "legislation"},
                )
            )

        return out


class CumhurbaskanligiAdapter(FailureRecorder):
    """Cumhurbaşkanlığı Kararnameleri ve Resmi Duyuruları."""

    slug = "cb-kararname"

    def __init__(
        self,
        slug: str = "cb-kararname",
        *,
        base_url: str = "https://www.tccb.gov.tr",
        http: HttpClient | None = None,
    ) -> None:
        super().__init__()
        self.slug = slug
        self.base_url = base_url.rstrip("/")
        self.http = http or HttpClient(
            respect_robots=False,
            user_agent=BROWSER_USER_AGENT,
            timeout=30.0,
            max_retries=4,
        )

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        url = f"{self.base_url}/basin-aciklamalari"
        try:
            resp = self.http.get(url, source_slug=self.slug)
            now = datetime.now(UTC)
            for match in _ANCHOR.finditer(resp.text):
                href, label = match.group(1), match.group(2)
                title = clean_text(label)
                if title and len(title) > 20:
                    full_url = (
                        href
                        if href.startswith("http")
                        else f"{self.base_url}/{href.lstrip('/')}"
                    )
                    items.append(
                        RawItem(
                            source_slug=self.slug,
                            url=full_url,
                            title=f"Cumhurbaşkanlığı: {title}",
                            published_at=now,
                            summary=f"Cumhurbaşkanlığı Açıklaması: {title}",
                            guid=full_url,
                            extra={"category": "atama_ve_kadro", "vertical": "legislation"},
                        )
                    )

        except Exception as exc:  # noqa: BLE001
            self.record_failure(url, exc)
            log.warning("cb_fetch_failed", url=url, error=type(exc).__name__)
        return items


registry.register("sayistay", SayistayAdapter)
registry.register("cumhurbaskanligi", CumhurbaskanligiAdapter)
