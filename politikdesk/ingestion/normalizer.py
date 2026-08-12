"""Normalizasyon ve saklama politikası (F1-08, F1-09).

F1-08 DoD: UTM parametreleri temizleniyor; tarihler UTC; Türkçe karakter
sorunları yok.

F1-09 DoD: `excerpt` ≤300 kr, `lead_paragraph` + `raw_purge_at`; kısıt DB
seviyesinde zorlanıyor; tam metin hiçbir alanda saklanmıyor.
"""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from politikdesk.ingestion.dedup import compute_simhash
from politikdesk.ingestion.models import NormalizedArticle, RawItem

# Spec §9.3 saklama politikası — bu sabitler DB CHECK kısıtlarıyla eşleşir.
EXCERPT_MAX_CHARS = 300
LEAD_MAX_CHARS = 1_000
RAW_RETENTION_DAYS = 30

# Takip parametreleri: aynı içerik farklı URL ile gelmesin (tekilleştirme
# doğruluğunu doğrudan etkiler).
_TRACKING_PREFIXES = ("utm_", "pk_", "mtm_", "hsa_", "vero_")
_TRACKING_EXACT = frozenset({
    "fbclid", "gclid", "gbraid", "wbraid", "msclkid", "igshid", "mc_cid",
    "mc_eid", "yclid", "ref", "ref_src", "referrer", "spm", "_ga", "_gl",
    "cmpid", "campaign_id", "source",
})

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def canonicalize_url(url: str) -> str:
    """URL'i tekilleştirmeye uygun kanonik biçime getirir.

    - şema ve host küçük harfe indirilir
    - takip parametreleri atılır
    - kalan sorgu parametreleri sıralanır (sıra farkı tekrar üretmesin)
    - fragment (#...) atılır
    - sondaki '/' kaldırılır (kök hariç)
    """
    parts = urlsplit(url.strip())

    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    # Varsayılan portlar kaldırılır
    for default in (":80", ":443"):
        if netloc.endswith(default):
            netloc = netloc[: -len(default)]

    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if not _is_tracking_param(k)
    ]
    query = urlencode(sorted(query_pairs))

    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    return urlunsplit((scheme, netloc, path, query, ""))


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    return lowered in _TRACKING_EXACT or lowered.startswith(_TRACKING_PREFIXES)


def clean_text(raw: str | None) -> str:
    """HTML etiketlerini atar, boşlukları sadeleştirir, Unicode'u normalize eder.

    NFC normalizasyonu Türkçe için kritiktir: 'İ' ve 'ı' gibi karakterler
    kaynağa göre birleşik veya ayrık kodlanmış gelebilir; normalize
    edilmezse aynı metin iki farklı hash üretir ve tekilleştirme çöker.
    """
    if not raw:
        return ""
    text = _HTML_TAG_RE.sub(" ", raw)
    # stdlib `html.unescape` tüm adlandırılmış ve sayısal varlıkları çözer.
    # Elle yazılmış kısa liste yetmiyordu: kurum akışlarında &rsquo; &ldquo;
    # &uuml; gibi varlıklar geçiyor ve başlıklara ham olarak sızıyordu.
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = unicodedata.normalize("NFC", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def clean_title(raw: str) -> str:
    """Başlıktan kaynak ekini temizler ("... - Dünya", "... | BloombergHT")."""
    title = clean_text(raw)
    title = re.sub(r"\s*[|\-–—]\s*[^|\-–—]{2,30}$", "", title) if len(title) > 40 else title
    return title.strip()


def make_excerpt(text: str, limit: int = EXCERPT_MAX_CHARS) -> str | None:
    """≤300 karakterlik alıntı üretir; kelime ortasından kesmez."""
    cleaned = clean_text(text)
    if not cleaned:
        return None
    if len(cleaned) <= limit:
        return cleaned

    truncated = cleaned[: limit - 1]
    last_space = truncated.rfind(" ")
    if last_space > limit * 0.6:
        truncated = truncated[:last_space]
    return truncated.rstrip(" ,;:") + "…"


def content_hash(title: str, excerpt: str | None) -> str:
    """Tam tekrar tespiti için içerik parmak izi (F1-10)."""
    payload = f"{clean_text(title)}\n{clean_text(excerpt or '')}".casefold()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize(
    item: RawItem,
    *,
    store_excerpt: bool = True,
    now: datetime | None = None,
    topics: tuple[str, ...] = (),
) -> NormalizedArticle:
    """RawItem'ı saklamaya hazır makaleye çevirir.

    `store_excerpt=False` (ToS `restricted`): alıntı üretilmez, yalnızca
    meta veri + link saklanır.
    """
    now = now or datetime.now(UTC)

    title = clean_title(item.title)
    summary = clean_text(item.summary)

    excerpt = make_excerpt(summary) if (store_excerpt and summary) else None
    # lead_paragraph işleme amaçlıdır ve TTL ile silinir; tam metin değildir.
    lead = summary[:LEAD_MAX_CHARS] if (store_excerpt and summary) else None

    published = item.published_at
    if published is not None and published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    elif published is not None:
        published = published.astimezone(UTC)

    return NormalizedArticle(
        source_slug=item.source_slug,
        canonical_url=canonicalize_url(item.url),
        title=title,
        excerpt=excerpt,
        lead_paragraph=lead,
        published_at=published,
        content_hash=content_hash(title, excerpt),
        simhash=compute_simhash(f"{title} {summary}"),
        lang=item.lang,
        raw_purge_at=now + timedelta(days=RAW_RETENTION_DAYS),
        topics=topics,
    )
