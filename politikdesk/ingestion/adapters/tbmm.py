"""TBMM Yasama, Genel Kurul Tutanağı ve Komisyon Adaptörü (S1 · Spec v3.4 §5, §8.3 R8).

Türkiye Büyük Millet Meclisi'nin birincil yasama ve denetim kayıtlarını toplar:
1. Kanun Teklifleri (yasama süreci, teklif sahibi, komisyon aşaması)
2. Genel Kurul Tutanakları (konuşma ve beyan metinleri, oylamalar)
3. Komisyon Gündemleri ve Takvimi (Plan ve Bütçe vb.)

Bu adaptör, Siyaset Dikeyinde R8 "beyan kaydı" kuralının ve vaat (promise)
iddialarının en temel birincil veri kaynağıdır (Tier 1).
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


class TbmmAdapter(FailureRecorder):
    """TBMM Kanun Teklifleri, Tutanaklar ve Komisyon Gündemi toplayıcısı."""

    slug = "tbmm"

    def __init__(
        self,
        slug: str = "tbmm",
        *,
        base_url: str = "https://www.tbmm.gov.tr",
        http: HttpClient | None = None,
        keyword_filter: list[str] | None = None,
        days_back: int = 3,
        feed_url: str | None = None,
    ) -> None:
        super().__init__()
        self.slug = slug
        self.base_url = base_url.rstrip("/")
        self.feed_url = feed_url
        self.http = http or HttpClient(
            respect_robots=False,
            user_agent=BROWSER_USER_AGENT,
            timeout=30.0,
            max_retries=4,
        )
        self.keyword_filter = [k.casefold() for k in (keyword_filter or [])]
        self.days_back = days_back

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()

        # 1. Kanun Teklifleri sayfası / akışı
        proposal_urls = [
            f"{self.base_url}/yasama/kanun-teklifleri",
            f"{self.base_url}/kanunteklifleri",
        ]
        if self.feed_url:
            proposal_urls.insert(0, self.feed_url)

        for url in proposal_urls[:2]:
            try:
                resp = self.http.get(url, source_slug=self.slug)
                parsed = self._parse_proposals(resp.text, url)
                for item in parsed:
                    if item.url not in seen:
                        seen.add(item.url)
                        items.append(item)
                if parsed:
                    break
            except Exception as exc:  # noqa: BLE001
                self.record_failure(url, exc)
                log.warning(
                    "tbmm_proposals_failed",
                    url=url,
                    error=type(exc).__name__,
                    detail=str(exc)[:200],
                )

        # 2. Tutanaklar (Son birleşim tutanağı özeti)
        tutanak_url = f"{self.base_url}/tutanaklar"
        try:
            resp = self.http.get(tutanak_url, source_slug=self.slug)
            parsed_tutanak = self._parse_tutanak(resp.text, tutanak_url)
            for item in parsed_tutanak:
                if item.url not in seen:
                    seen.add(item.url)
                    items.append(item)
        except Exception as exc:  # noqa: BLE001
            self.record_failure(tutanak_url, exc)
            log.warning("tbmm_tutanak_failed", url=tutanak_url, error=type(exc).__name__)

        return items

    def _parse_proposals(self, html: str, base_page_url: str) -> list[RawItem]:
        out: list[RawItem] = []
        now = datetime.now(UTC)

        for match in _ANCHOR.finditer(html):
            href, label = match.group(1), match.group(2)
            title = clean_text(label)
            if not title or len(title) < 15:
                continue

            # Kanun teklifi / torba kanun / yasa başlıkları
            law_keywords = ("kanun", "teklif", "değişiklik", "kanunu", "taslak")
            if any(k in title.casefold() for k in law_keywords):
                if not self._passes_filter(title):
                    continue
                url = href if href.startswith("http") else f"{self.base_url}/{href.lstrip('/')}"
                out.append(
                    RawItem(
                        source_slug=self.slug,
                        url=url,
                        title=title[:500],
                        published_at=now,
                        summary=f"TBMM Yasama Süreci: {title}",
                        guid=url,
                        extra={"category": "kanun_teklifi", "vertical": "legislation"},
                    )
                )
        return out

    def _parse_tutanak(self, html: str, base_page_url: str) -> list[RawItem]:
        out: list[RawItem] = []
        now = datetime.now(UTC)

        for match in _ANCHOR.finditer(html):
            href, label = match.group(1), match.group(2)
            title = clean_text(label)
            if "tutanak" in title.casefold() or "birleşim" in title.casefold():
                if not self._passes_filter(title):
                    continue
                url = href if href.startswith("http") else f"{self.base_url}/{href.lstrip('/')}"
                out.append(
                    RawItem(
                        source_slug=self.slug,
                        url=url,
                        title=f"TBMM Genel Kurul Tutanağı: {title}",
                        published_at=now,
                        summary=f"TBMM Genel Kurulu Birleşim Tutanağı: {title}",
                        guid=url,
                        extra={"category": "genel_kurul_tutanak", "vertical": "legislation"},
                    )
                )
        return out

    def _passes_filter(self, title: str) -> bool:
        if not self.keyword_filter:
            return True
        folded = title.casefold()
        return any(k in folded for k in self.keyword_filter)


registry.register("tbmm", TbmmAdapter)
