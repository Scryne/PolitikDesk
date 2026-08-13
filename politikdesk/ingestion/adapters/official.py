"""Resmî kurum akış adaptörleri (F1-03).

Dört Tier 1 kaynak, dört farklı erişim biçimi gerektiriyor:

    TCMB          RSS var       -> RssAdapter (adapters/rss.py)
    Resmî Gazete  RSS var       -> RssAdapter + konu filtresi
    TÜİK          RSS YOK       -> TuikAdapter (bülten listesi)
    Hazine        RSS YOK       -> WordPressRestAdapter (B-43)

HTML liste ayrıştırması stdlib `html.parser` ile yapılır — ek bağımlılık
yok ve davranış tahmin edilebilir.

⚠️ Bu adaptörler **liste sayfası** okur; makale gövdesine girmez.
Spec §9.3: tam metin hiçbir zaman saklanmaz.
"""

from __future__ import annotations

import html as html_mod
import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin

from politikdesk.ingestion.adapters.base import FailureRecorder, registry
from politikdesk.ingestion.http import HttpClient
from politikdesk.ingestion.models import RawItem
from politikdesk.observability import get_logger

log = get_logger(__name__)


class _LinkHarvester(HTMLParser):
    """Sayfadaki <a href> bağlantılarını ve metinlerini toplar."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._href = href
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            text = " ".join("".join(self._chunks).split())
            if text:
                self.links.append((self._href, text))
            self._href = None
            self._chunks = []


def harvest_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """(mutlak_url, bağlantı_metni) çiftlerini döndürür."""
    parser = _LinkHarvester()
    parser.feed(html)
    return [(urljoin(base_url, href), text) for href, text in parser.links]


# TÜİK bülten URL kalıbı: .../Bulten/Index?p=<Slug>-<Ay>-<Yil>-<ID>
_TUIK_BULLETIN_RE = re.compile(r"/Bulten/Index\?p=(?P<slug>[\w%\-]+?)-(?P<id>\d+)$")

_TR_MONTHS = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5,
    "mayis": 5, "haziran": 6, "temmuz": 7, "ağustos": 8, "agustos": 8,
    "eylül": 9, "eylul": 9, "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12,
    "aralik": 12,
}


class TuikAdapter(FailureRecorder):
    """TÜİK haber bültenleri (F1-03).

    TÜİK bir RSS akışı yayımlamaz. Bültenler veri portalındaki liste
    sayfasında yer alır ve tekil URL'leri `?p=<Slug>-<Donem>-<ID>` kalıbını
    izler. Adaptör liste sayfasındaki bülten bağlantılarını toplar.

    Liste sayfası JavaScript ile yükleniyorsa `fetch()` boş döner ve
    bunu **uyarı olarak loglar** — sessizce başarılı görünmez.
    `scripts/discover_feeds.py` bu durumda alternatif uçları arar.
    """

    slug = "tuik"

    def __init__(
        self,
        slug: str = "tuik",
        *,
        index_urls: list[str] | None = None,
        base_url: str = "https://veriportali.tuik.gov.tr",
        http: HttpClient | None = None,
    ) -> None:
        super().__init__()
        self.slug = slug
        self.base_url = base_url
        self.index_urls = index_urls or [
            "https://veriportali.tuik.gov.tr/Bulten/Index",
            "https://data.tuik.gov.tr/Bulten/Index",
        ]
        self.http = http or HttpClient()

    def fetch(self) -> list[RawItem]:
        for index_url in self.index_urls:
            try:
                response = self.http.get(index_url, source_slug=self.slug)
            except Exception as exc:  # noqa: BLE001
                self.record_failure(index_url, exc)
                log.warning("tuik_index_failed", url=index_url,
                            error=type(exc).__name__, detail=str(exc)[:200])
                continue

            items = self.parse(response.text, base_url=index_url)
            if items:
                return items
            self.note_failure(f"{index_url}: HTTP 200 ama bülten bağlantısı yok")
            log.warning(
                "tuik_index_empty",
                url=index_url,
                hint="Liste JavaScript ile yükleniyor olabilir. "
                     "`python -m scripts.discover_feeds tuik` ile JSON ucunu arayın.",
            )
        return []

    def parse(self, html: str, *, base_url: str) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()

        for url, text in harvest_links(html, base_url):
            if not _TUIK_BULLETIN_RE.search(url):
                continue
            if url in seen:
                continue
            seen.add(url)

            title = " ".join(text.split())
            if len(title) < 8:
                continue

            items.append(
                RawItem(
                    source_slug=self.slug,
                    url=url,
                    title=title,
                    published_at=extract_period_from_title(title),
                    summary=None,
                    guid=url,
                )
            )
        return items


class GenericHtmlAdapter(FailureRecorder):
    """Liste sayfasından duyuru bağlantısı toplayan genel adaptör (F1-03).

    Hazine gibi RSS yayımlamayan kurumlar için. `link_pattern` ile hangi
    bağlantıların duyuru olduğu belirtilir; kalıp verilmezse aynı host
    altındaki, yeterince uzun metinli bağlantılar alınır.
    """

    def __init__(
        self,
        slug: str,
        *,
        index_urls: list[str],
        base_url: str = "",
        link_pattern: str | None = None,
        min_title_len: int = 15,
        http: HttpClient | None = None,
    ) -> None:
        super().__init__()
        self.slug = slug
        self.index_urls = index_urls
        self.base_url = base_url
        self.link_re = re.compile(link_pattern) if link_pattern else None
        self.min_title_len = min_title_len
        self.http = http or HttpClient()

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        for index_url in self.index_urls:
            try:
                response = self.http.get(index_url, source_slug=self.slug)
            except Exception as exc:  # noqa: BLE001
                self.record_failure(index_url, exc)
                log.warning("html_index_failed", source=self.slug, url=index_url,
                            error=type(exc).__name__, detail=str(exc)[:200])
                continue
            items.extend(self.parse(response.text, base_url=index_url))

        if not items:
            self.note_failure(
                f"{self.slug}: {len(self.index_urls)} liste sayfasının hiçbirinde "
                "duyuru bağlantısı bulunamadı"
            )
            log.warning("html_index_empty", source=self.slug,
                        hint="`python -m scripts.discover_feeds` ile uç arayın.")
        return items

    def parse(self, html: str, *, base_url: str) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()

        for url, text in harvest_links(html, base_url):
            title = " ".join(text.split())
            if len(title) < self.min_title_len:
                continue
            if self.link_re and not self.link_re.search(url):
                continue
            if not self.link_re and self.base_url and not url.startswith(self.base_url):
                continue
            if url in seen:
                continue
            seen.add(url)

            items.append(
                RawItem(
                    source_slug=self.slug,
                    url=url,
                    title=title,
                    published_at=extract_period_from_title(title),
                    guid=url,
                )
            )
        return items


def strip_html(raw: str) -> str:
    """Etiketleri atar, varlıkları çözer, boşlukları tekilleştirir.

    WordPress `title.rendered` / `excerpt.rendered` alanları HTML döner
    (`<p>...</p>`, `&#8217;`). Ham hâliyle saklanırsa hem başlık kirlenir
    hem de içerik özeti kaçak etiket taşır.
    """
    text = re.sub(r"<[^>]+>", " ", raw)
    return " ".join(html_mod.unescape(text).split())


class WordPressRestAdapter(FailureRecorder):
    """WordPress REST API yayımlayan kurum siteleri (B-43).

    **Neden var.** Hazine'nin duyuru sayfası bir React uygulamasıdır;
    sunucu yalnızca "You need to enable JavaScript to run this app."
    kabuğunu döner. `GenericHtmlAdapter` bu kabukta bağlantı bulamadığı
    için kaynak aylarca **HTTP 200 döndürüp 0 öğe** üretti — sağlık
    panosunda kırmızıydı ama arıza kaynağın kendisinde değil, erişim
    biçimindeydi.

    Uygulamayı besleyen uç bir WordPress REST koleksiyonudur ve JSON
    döner. `robots.txt` (13 Ağu 2026) `Disallow:` ile boştur — tüm yollar
    açıktır.

    ⚠️ `link` alanı arka uç konağını (`api.hmb.gov.tr`) gösterir; kullanıcı
    bunu açamaz. Genel adres `base_url` + `public_path` + slug'tan kurulur.
    """

    def __init__(
        self,
        slug: str,
        *,
        api_url: str,
        base_url: str = "",
        public_path: str = "/duyuru/",
        per_page: int = 20,
        http: HttpClient | None = None,
    ) -> None:
        super().__init__()
        self.slug = slug
        self.api_url = api_url
        self.base_url = base_url.rstrip("/")
        self.public_path = public_path
        self.per_page = per_page
        self.http = http or HttpClient()

    def fetch(self) -> list[RawItem]:
        url = f"{self.api_url}?per_page={self.per_page}"
        try:
            response = self.http.get(url, source_slug=self.slug)
        except Exception as exc:  # noqa: BLE001
            self.record_failure(url, exc)
            log.warning("wp_rest_failed", source=self.slug, url=url,
                        error=type(exc).__name__, detail=str(exc)[:200])
            return []

        items = self.parse(response.text)
        if not items:
            self.note_failure(f"{url}: HTTP 200 ama kullanılabilir kayıt yok")
            log.warning("wp_rest_empty", source=self.slug, url=url,
                        hint="Uç JSON dizisi dönmedi ya da tüm kayıtlar eksik alanlı.")
        return items

    def parse(self, payload: str) -> list[RawItem]:
        """JSON gövdesini RawItem listesine çevirir. Ağ erişimi gerektirmez."""
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            log.warning("wp_rest_bad_json", source=self.slug, detail=str(exc)[:200])
            return []
        if not isinstance(data, list):
            return []

        items: list[RawItem] = []
        for post in data:
            if not isinstance(post, dict):
                continue
            item = self._parse_post(post)
            if item is not None:
                items.append(item)
        return items

    def _parse_post(self, post: dict) -> RawItem | None:
        title = strip_html(str(post.get("title", {}).get("rendered", "")))
        post_slug = str(post.get("slug") or "").strip()
        if not title or not post_slug:
            # Eksik alanlı kayıt atlanır — tüm koleksiyonu düşürmez.
            return None

        summary = strip_html(str(post.get("excerpt", {}).get("rendered", ""))) or None

        return RawItem(
            source_slug=self.slug,
            url=f"{self.base_url}{self.public_path}{post_slug}",
            title=title,
            published_at=_parse_wp_date(post.get("date_gmt")),
            summary=summary,
            # WordPress `id` kalıcıdır; slug düzenlenebilir. Tekilleştirme
            # kimliği bu yüzden id'den kurulur.
            guid=f"{self.slug}:{post.get('id')}",
        )


def _parse_wp_date(raw: object) -> datetime | None:
    """`date_gmt` alanını UTC datetime'a çevirir.

    WordPress bu alanı zaman dilimi eki OLMADAN yazar ("2026-08-11T14:10:55")
    ama değer UTC'dir. `fromisoformat` naive bir nesne döndürür; UTC etiketi
    burada elle takılır, aksi halde aşağıdaki karşılaştırmalar patlar.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip())
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def extract_period_from_title(title: str) -> datetime | None:
    """Başlıktaki dönem bilgisini tarihe çevirir.

    "Tüketici Fiyat Endeksi, Temmuz 2026" -> 2026-07-01
    Resmî kurum bültenlerinde yayın tarihi başlıkta dönem olarak geçer;
    bu, gerçek yayın anı değil **veri dönemidir** ve kümeleme için
    dönemin kendisi daha bilgilendiricidir.
    """
    match = re.search(r"([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(\d{4})", title)
    if not match:
        return None
    month = _TR_MONTHS.get(match.group(1).casefold())
    if not month:
        return None
    year = int(match.group(2))
    if not (2000 <= year <= 2100):
        return None
    return datetime(year, month, 1, tzinfo=UTC)


registry.register("tuik", TuikAdapter)
registry.register("generic_html", GenericHtmlAdapter)
registry.register("wp_rest", WordPressRestAdapter)
