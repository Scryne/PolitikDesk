"""X / Twitter Hesap İzleme Adaptörü ve Epistemik Koruma Katmanı (Spec v3.5 §9.4, §12.4).

3 Kademeli Mimari:
  1. Birincil: RSSHub / Nitter / RSS Bridge Köprüsü
  2. İkincil: Public oEmbed ve Webhook İstemcisi
  3. Yedek / Fallback: Yapılandırılmış Geri Çekilme (Backoff) ve Ayrıştırıcı

Epistemik ve Hukuki İlkeler (Spec §9.4 / R7 / TCK 217/A):
  - X gönderileri HER ZAMAN Tier 4 (social) ve kind='social' olarak damgalanır.
  - X gönderilerinden çıkarılan tüm iddialar 'attribution' (aktör beyanı/iddiası) türündedir.
  - R7 kuralı uyarınca yalnızca sosyal medya kanıtı içeren iddia ASLA strongly_corroborated
    (🟢) olamaz.
  - Flood / Thread birleştirici, zincir tweet'leri tek bir tutarlı analitik birimde toplar.
  - Alıntı ve yanıtlar tespit edilerek polemik ve duruş değişiklikleri için metaveri üretir.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import quote
from xml.etree import ElementTree

from politikdesk.ingestion.adapters.base import registry
from politikdesk.ingestion.http import HttpClient
from politikdesk.ingestion.models import RawItem
from politikdesk.observability import get_logger

log = get_logger(__name__)

_DATE_PATTERNS = (
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S GMT",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
)


def _parse_pubdate(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    for pattern in _DATE_PATTERNS:
        try:
            parsed = datetime.strptime(text, pattern)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            continue
    return None


@dataclass
class TweetItem:
    tweet_id: str
    author_handle: str
    text: str
    published_at: datetime
    url: str
    in_reply_to_tweet_id: str | None = None
    quoted_tweet_url: str | None = None
    quoted_text: str | None = None
    media_urls: list[str] = field(default_factory=list)


def aggregate_threads(
    tweets: list[TweetItem],
    max_thread_gap_hours: int = 12,
    default_source_slug: str | None = None,
) -> list[RawItem]:
    """Bir yazarın peş peşe attığı zincir (flood/thread) tweet'leri birleştirir."""
    if not tweets:
        return []

    # Tarihe göre sırala
    sorted_tweets = sorted(tweets, key=lambda t: t.published_at)
    threads: list[list[TweetItem]] = []

    for tweet in sorted_tweets:
        placed = False
        # Son thread ile bağlantılı mı kontrol et
        if threads:
            last_thread = threads[-1]
            last_tweet = last_thread[-1]
            if (
                last_tweet.author_handle.lower() == tweet.author_handle.lower()
                and (tweet.published_at - last_tweet.published_at).total_seconds()
                <= max_thread_gap_hours * 3600
                and (
                    tweet.in_reply_to_tweet_id == last_tweet.tweet_id
                    or tweet.in_reply_to_tweet_id is not None
                    or tweet.text.startswith(("1/", "2/", "3/", "4/", "5/", "...", ">>"))
                )
            ):
                last_thread.append(tweet)
                placed = True

        if not placed:
            threads.append([tweet])

    raw_items: list[RawItem] = []
    for thread in threads:
        first = thread[0]
        if len(thread) == 1:
            full_text = first.text
            title = f"@{first.author_handle}: {first.text[:80]}"
        else:
            full_text = "\n\n".join(
                f"[{i + 1}/{len(thread)}] {t.text}" for i, t in enumerate(thread)
            )
            title = f"@{first.author_handle} (Flood {len(thread)} Tweet): {first.text[:70]}"

        # Alıntı ve yanıt referansları
        quotes = [t.quoted_tweet_url for t in thread if t.quoted_tweet_url]
        quoted_texts = [t.quoted_text for t in thread if t.quoted_text]

        slug = default_source_slug or f"x-{first.author_handle.lower()}"

        raw_items.append(
            RawItem(
                source_slug=slug,
                url=first.url,
                title=title,
                published_at=first.published_at,
                summary=full_text[:400],
                guid=first.url,
                extra={
                    "is_social": True,
                    "access_method": "social",
                    "author_handle": first.author_handle,
                    "is_thread": len(thread) > 1,
                    "tweet_count": len(thread),
                    "tweet_ids": [t.tweet_id for t in thread],
                    "quoted_tweet_urls": quotes,
                    "quoted_texts": quoted_texts,
                    "tier": 4,
                    "claim_type_enforced": "attribution",
                    "full_text": full_text,
                },
            )
        )

    return raw_items


class TwitterAdapter:
    """X / Twitter hesap ve liste izleme adaptörü.

    3 Kademeli Dayanıklılık ve Sağlık İzleme (Spec v3.5 §9.4):
      - 1. Kademe: RSSHub / Nitter / RSS Bridge (Hesap veya Liste)
      - 2. Kademe: Kamuya Açık oEmbed (Yalnızca tekil hesaplar için)
      - 3. Kademe: Yapılandırılmış Geri Çekilme (Backoff) / Sentetik Fallback
    """

    def __init__(
        self,
        slug: str,
        handle: str | None = None,
        *,
        list_id: str | None = None,
        bridge_url: str | None = None,
        base_url: str = "https://x.com",
        http: HttpClient | None = None,
        max_consecutive_failures: int = 3,
    ) -> None:
        self.slug = slug
        self.handle = (handle or "").strip("@")
        self.list_id = list_id
        self.base_url = base_url
        env_bridge = (
            os.getenv("PD_TWITTER_BRIDGE_URL") or os.getenv("PD_RSSHUB_BRIDGE_URL") or ""
        ).strip()
        self.bridge_url = bridge_url or (
            env_bridge if env_bridge else "http://127.0.0.1:1200"
        )
        self.http = http or HttpClient(
            respect_robots=False,
            enforce_ssrf=False,
            timeout=25.0,
            connect_timeout=8.0,
            read_timeout=18.0,
            enable_jitter=True,
        )
        self.max_consecutive_failures = max_consecutive_failures
        self._consecutive_failures = 0
        self._is_degraded = False
        self._failures: list[str] = []

    @property
    def is_degraded(self) -> bool:
        """Ardışık başarısızlık eşiği aşıldığında kaynak 'degraded' (bozulmuş) kabul edilir."""
        return self._is_degraded or self._consecutive_failures >= self.max_consecutive_failures

    def drain_failures(self) -> list[str]:
        """Boru hattı için hata defterini boşaltır (B-80)."""
        drained = self._failures
        self._failures = []
        return drained

    def fetch(self) -> list[RawItem]:
        """Hesaptan veya listeden tweet'leri toplar ve thread birleştirmesi uygular."""
        tweets = self._fetch_via_bridge()
        if not tweets and not self.list_id and self.handle:
            log.info("twitter_fallback_oembed_triggered", handle=self.handle)
            tweets = self._fetch_via_oembed()

        if tweets:
            self._record_success()
        else:
            target = f"liste #{self.list_id}" if self.list_id else f"@{self.handle}"
            self._record_failure(f"X {target} için hiçbir kademeden veri alınamadı.")

        return aggregate_threads(tweets, default_source_slug=self.slug)

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._is_degraded = False

    def _record_failure(self, message: str) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.max_consecutive_failures:
            self._is_degraded = True
            log.warning(
                "twitter_source_degraded",
                handle=self.handle,
                list_id=self.list_id,
                consecutive_failures=self._consecutive_failures,
            )
        self._failures.append(message)

    def _fetch_via_bridge(self) -> list[TweetItem]:
        """Birincil yöntem: RSSHub / RSS Bridge üzerinden XML akışını çeker."""
        if self.list_id:
            feed_endpoint = f"{self.bridge_url.rstrip('/')}/twitter/list/{self.list_id}"
        else:
            feed_endpoint = f"{self.bridge_url.rstrip('/')}/twitter/user/{quote(self.handle)}"

        try:
            resp = self.http.get(feed_endpoint, source_slug=self.slug)
            if resp.status_code != 200:
                self._failures.append(f"Bridge HTTP {resp.status_code} döndü: {feed_endpoint}")
                return []

            root = ElementTree.fromstring(resp.text)
            tweets: list[TweetItem] = []

            for item in root.findall("./channel/item"):
                title_elem = item.find("title")
                desc_elem = item.find("description")
                link_elem = item.find("link")
                pubdate_elem = item.find("pubDate")

                text = (desc_elem.text if desc_elem is not None and desc_elem.text else "") or (
                    title_elem.text if title_elem is not None and title_elem.text else ""
                )
                # HTML etiketlerini temizle
                clean_text = re.sub(r"<[^>]+>", " ", text).strip()
                clean_text = " ".join(clean_text.split())

                link = (
                    link_elem.text.strip()
                    if link_elem is not None and link_elem.text
                    else (
                        f"https://x.com/i/lists/{self.list_id}"
                        if self.list_id
                        else f"https://x.com/{self.handle}"
                    )
                )
                pub_date = _parse_pubdate(
                    pubdate_elem.text if pubdate_elem is not None else None
                ) or datetime.now(UTC)

                # Tweet linkinden yazar handle'ını ayıkla
                author_match = re.search(
                    r"https?://(?:x\.com|twitter\.com)/([A-Za-z0-9_]+)/status/\d+", link
                )
                author = author_match.group(1) if author_match else (self.handle or "x")

                # Tweet ID'sini URL'den çıkar
                tweet_id_match = re.search(r"/status/(\d+)", link)
                tweet_id = (
                    tweet_id_match.group(1)
                    if tweet_id_match
                    else str(int(pub_date.timestamp()))
                )

                # Alıntı tweet URL'si var mı?
                quote_match = re.search(
                    r"https?://(?:x\.com|twitter\.com)/[A-Za-z0-9_]+/status/(\d+)", clean_text
                )
                quoted_url = (
                    quote_match.group(0) if quote_match and quote_match.group(0) != link else None
                )

                tweets.append(
                    TweetItem(
                        tweet_id=tweet_id,
                        author_handle=author,
                        text=clean_text,
                        published_at=pub_date,
                        url=link,
                        quoted_tweet_url=quoted_url,
                    )
                )

            return tweets
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "twitter_bridge_fetch_failed",
                handle=self.handle,
                list_id=self.list_id,
                error=str(exc)[:200],
            )
            self._failures.append(f"Bridge istisnası: {type(exc).__name__}: {str(exc)[:200]}")
            return []

    def _fetch_via_oembed(self) -> list[TweetItem]:
        """İkincil yöntem: Kamuya açık Twitter oEmbed uç noktasından tweet ayrıştırma."""
        handle_url = quote(f"https://x.com/{self.handle}")
        oembed_url = f"https://publish.twitter.com/oembed?url={handle_url}&omit_script=true"
        try:
            resp = self.http.get(oembed_url, source_slug=self.slug)
            if resp.status_code != 200:
                self._failures.append(f"oEmbed HTTP {resp.status_code} döndü: {oembed_url}")
                return []

            data = None
            if hasattr(resp, "json") and callable(resp.json):
                try:
                    data = resp.json()
                except Exception:
                    data = None
            if data is None:
                import json

                try:
                    data = json.loads(resp.text)
                except Exception:
                    self._failures.append(f"oEmbed JSON ayrıştırılamadı: {oembed_url}")
                    return []

            if not isinstance(data, dict):
                return []

            html = data.get("html", "")
            if not html:
                return []

            tweets: list[TweetItem] = []
            status_matches = list(
                re.finditer(
                    r'<blockquote[^>]*>(.*?)&mdash;.*?<a\s+href="(?P<url>https?://(?:twitter\.com|x\.com)/(?P<user>[^/]+)/status/(?P<id>\d+))"[^>]*>(?P<date>[^<]*)</a>',
                    html,
                    re.DOTALL | re.IGNORECASE,
                )
            )

            for m in status_matches:
                raw_body = m.group(1)
                p_match = re.search(r"<p[^>]*>(.*?)</p>", raw_body, re.DOTALL | re.IGNORECASE)
                text = p_match.group(1) if p_match else raw_body
                clean_text = re.sub(r"<[^>]+>", " ", text).strip()
                clean_text = " ".join(clean_text.split())

                tweet_id = m.group("id")
                url = m.group("url")
                date_str = m.group("date").strip()
                pub_date = _parse_pubdate(date_str) or datetime.now(UTC)

                quote_match = re.search(
                    r"https?://(?:x\.com|twitter\.com)/[A-Za-z0-9_]+/status/(\d+)", clean_text
                )
                quoted_url = (
                    quote_match.group(0) if quote_match and quote_match.group(0) != url else None
                )

                tweets.append(
                    TweetItem(
                        tweet_id=tweet_id,
                        author_handle=self.handle,
                        text=clean_text,
                        published_at=pub_date,
                        url=url,
                        quoted_tweet_url=quoted_url,
                    )
                )

            if not tweets and ("twitter-tweet" in html or data.get("author_name")):
                clean_text = re.sub(r"<[^>]+>", " ", html).strip()
                clean_text = " ".join(clean_text.split())
                if clean_text:
                    url_match = re.search(
                        r"https?://(?:twitter\.com|x\.com)/[A-Za-z0-9_]+/status/(\d+)", html
                    )
                    tweet_id = (
                        url_match.group(1)
                        if url_match
                        else str(int(datetime.now(UTC).timestamp()))
                    )
                    tweet_url = (
                        url_match.group(0)
                        if url_match
                        else f"https://x.com/{self.handle}/status/{tweet_id}"
                    )
                    tweets.append(
                        TweetItem(
                            tweet_id=tweet_id,
                            author_handle=self.handle,
                            text=clean_text,
                            published_at=datetime.now(UTC),
                            url=tweet_url,
                        )
                    )

            return tweets
        except Exception as exc:  # noqa: BLE001
            log.warning("twitter_oembed_fetch_failed", handle=self.handle, error=str(exc)[:200])
            self._failures.append(f"oEmbed istisnası: {type(exc).__name__}: {str(exc)[:200]}")
            return []


registry.register("twitter", TwitterAdapter)

