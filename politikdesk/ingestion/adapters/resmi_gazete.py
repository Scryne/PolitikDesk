"""Resmî Gazete günlük fihristi (F5-20 · B-44'ü kapatır).

**RSS YOKTUR.** `config/sources.yml` üç faz boyunca
`https://www.resmigazete.gov.tr/rss` adresini akış sanıyordu; o adres
RSS değil HTML döndürüyor (ölçüldü: 200 KB, sıfır `<item>`).

Gerçek yapı **günlük fihrist** sayfasıdır:

    /fihrist?tarih=YYYY-MM-DD

Sayfadaki her kalem mutlak adresli bir bağlantıdır:

    https://www.resmigazete.gov.tr/eskiler/2026/08/20260813-0.pdf
    https://www.resmigazete.gov.tr/eskiler/2026/08/20260813-1.htm

`GenericHtmlAdapter` bu sayfada işe yaramaz: genel bağlantı toplayıcısı
gezinti bağlantılarını ("Mükerrer Arşivi", "Resmî Gazete Tarihçesi")
kalem sanıyor. Bu yüzden kalem adresinin biçimi burada AÇIKÇA aranır.

**Konu filtresi zorunludur.** Resmî Gazete günde onlarca kalem yayımlar
ve bunların çoğu makro ekonomiyle ilgisizdir (üniversite yönetmelikleri,
atama kararları). Filtresiz toplama `articles` tablosunu alakasız kayıtla
doldurur ve embedding maliyetini boşa harcar — `sources.yml` bunu
`keyword_filter` ile veriyor.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from html import unescape

from politikdesk.ingestion.adapters.base import FailureRecorder, registry
from politikdesk.ingestion.http import BROWSER_USER_AGENT, HttpClient
from politikdesk.ingestion.models import RawItem
from politikdesk.observability import get_logger

log = get_logger(__name__)

# Bir KALEM adresi: .../eskiler/YYYY/MM/YYYYMMDD-<sira>.<uzanti>
# Sıra numarasız olan (20260813.pdf) sayının TAMAMIDIR, tek kalem değil.
_ITEM_HREF = re.compile(
    r"/eskiler/\d{4}/\d{2}/\d{8}-\d+\.(?:htm|html|pdf)$", re.IGNORECASE
)
_ANCHOR = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")


def clean_item_title(raw: str) -> str:
    """Bağlantı metnini başlığa çevirir.

    Fihristte kalemler "–– " ön ekiyle listelenir; bu bir başlık parçası
    değil, listeleme işaretidir.
    """
    text = unescape(_TAGS.sub("", raw))
    text = re.sub(r"\s+", " ", text).strip()
    return text.lstrip("–—-").strip()


class ResmiGazeteAdapter(FailureRecorder):
    """Günlük fihristten kalem bağlantılarını toplar."""

    slug = "resmi-gazete"

    def __init__(
        self,
        slug: str = "resmi-gazete",
        *,
        base_url: str = "https://www.resmigazete.gov.tr",
        http: HttpClient | None = None,
        keyword_filter: list[str] | None = None,
        days_back: int = 1,
    ) -> None:
        super().__init__()
        self.slug = slug
        self.base_url = base_url.rstrip("/")
        # Fihrist sayfası için gov.tr WAF bot engeline takılmamak adına
        # tarayıcı UA ve robots bypass kullanılır; istekler normalde ~100-300 ms'de döner.
        # Sunucu takılmalarında worker'ı kilitlememek için granüler timeout ve jitter kullanılır.
        self.http = http or HttpClient(
            respect_robots=False,
            user_agent=BROWSER_USER_AGENT,
            timeout=15.0,
            connect_timeout=5.0,
            read_timeout=10.0,
            write_timeout=5.0,
            pool_timeout=5.0,
            max_retries=3,
            enable_jitter=True,
        )
        self.keyword_filter = [k.casefold() for k in (keyword_filter or [])]
        # Gazete sabaha karşı yayımlanır; turun saatine göre "bugün" henüz
        # boş olabilir. Bir gün geriye bakmak boş turu önler.
        self.days_back = days_back


    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()

        for offset in range(self.days_back + 1):
            day = date.today() - timedelta(days=offset)
            url = f"{self.base_url}/fihrist?tarih={day.isoformat()}"
            try:
                response = self.http.get(url, source_slug=self.slug)
            except Exception as exc:  # noqa: BLE001
                # Yutulan istisna KAYDEDİLİR; yoksa boş tur "başarılı"
                # görünür ve sağlık panosu yanılır (B-80).
                self.record_failure(url, exc)
                log.warning("resmi_gazete_index_failed", url=url,
                            error=type(exc).__name__, detail=str(exc)[:200])
                continue

            for item in self._parse(response.text, day):
                if item.url in seen:
                    continue
                seen.add(item.url)
                items.append(item)

        if not items:
            log.warning("resmi_gazete_empty", days_back=self.days_back)
        return items

    def _parse(self, html: str, day: date) -> list[RawItem]:
        out: list[RawItem] = []
        published = datetime(day.year, day.month, day.day, tzinfo=UTC)

        for match in _ANCHOR.finditer(html):
            href, label = match.group(1), match.group(2)
            if not _ITEM_HREF.search(href):
                continue

            title = clean_item_title(label)
            if not title or title.casefold() == "pdf görüntüle":
                continue
            if not self._passes_keyword_filter(title):
                continue

            url = href if href.startswith("http") else f"{self.base_url}{href}"
            out.append(
                RawItem(
                    source_slug=self.slug,
                    url=url,
                    title=title[:500],
                    published_at=published,
                    summary=None,   # fihrist özet vermez; başlık kalemin kendisidir
                    guid=url,
                )
            )
        return out

    def _passes_keyword_filter(self, title: str) -> bool:
        if not self.keyword_filter:
            return True
        folded = title.casefold()
        return any(keyword in folded for keyword in self.keyword_filter)


registry.register("resmi_gazete", ResmiGazeteAdapter)
