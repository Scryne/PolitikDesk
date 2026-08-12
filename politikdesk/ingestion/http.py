"""Kibarlık (politeness) katmanı (F1-07).

DoD: kaynak başına dakikada azami istek sınırı uygulanıyor; 429/503'te
üstel geri çekilme.

Spec §9.3 madde 4: toplu izinsiz scraping hiçbir fazda kullanılmaz.
Bu katman "izinli erişimi kibarca yap"manın aracıdır — hız kazanmanın
değil.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from politikdesk.observability import get_logger

log = get_logger(__name__)

USER_AGENT = (
    "PolitikDeskBot/0.1 (+kisisel arastirma araci; "
    "kaynak gostererek alinti yapar; iletisim: repo sahibi)"
)

DEFAULT_TIMEOUT = 20.0
DEFAULT_MAX_RETRIES = 4
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class RateLimiter:
    """Kaynak (host) başına dakikada azami istek sayısı."""

    def __init__(self, max_per_minute: int = 12) -> None:
        self.max_per_minute = max_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def acquire(self, key: str) -> float:
        """Gerekirse bekler. Beklenen saniyeyi döndürür."""
        waited = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                window = self._hits[key]
                while window and now - window[0] > 60.0:
                    window.popleft()
                if len(window) < self.max_per_minute:
                    window.append(now)
                    return waited
                sleep_for = 60.0 - (now - window[0]) + 0.01
            time.sleep(sleep_for)
            waited += sleep_for


class RobotsCache:
    """`robots.txt` saygısı. Alınamazsa erişime izin verilir (kısıt beyan
    edilmemiş sayılır), ancak bu durum loglanır."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client
        self._cache: dict[str, RobotFileParser | None] = {}
        self._lock = threading.Lock()

    def allowed(self, url: str, user_agent: str = USER_AGENT) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        with self._lock:
            if origin not in self._cache:
                self._cache[origin] = self._load(origin)
            parser = self._cache[origin]

        if parser is None:
            return True
        return parser.can_fetch(user_agent, url)

    def _load(self, origin: str) -> RobotFileParser | None:
        try:
            response = self._client.get(f"{origin}/robots.txt", timeout=10.0)
            if response.status_code != 200:
                log.info("robots_not_published", origin=origin,
                         status=response.status_code)
                return None
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
            return parser
        except Exception:  # noqa: BLE001
            log.info("robots_fetch_failed", origin=origin)
            return None


@dataclass
class HttpClient:
    """Kibar HTTP istemcisi: UA, oran sınırı, robots, üstel geri çekilme."""

    max_per_minute: int = 12
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    respect_robots: bool = True

    def __post_init__(self) -> None:
        self._client = httpx.Client(
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.9",
                "Accept-Language": "tr-TR,tr;q=0.9",
            },
            timeout=self.timeout,
            follow_redirects=True,
        )
        self._limiter = RateLimiter(self.max_per_minute)
        self._robots = RobotsCache(self._client)

    def get(self, url: str, *, source_slug: str = "") -> httpx.Response:
        """Kibarca GET. 429/503'te üstel geri çekilme ile yeniden dener."""
        if self.respect_robots and not self._robots.allowed(url):
            raise RobotsDisallowed(f"robots.txt bu yolu yasaklıyor: {url}")

        host = urlparse(url).netloc
        self._limiter.acquire(host)

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = self._client.get(url)
            except httpx.HTTPError as exc:
                last_error = exc
                self._backoff(attempt, url, reason=type(exc).__name__)
                continue

            if response.status_code in RETRYABLE_STATUS:
                retry_after = _parse_retry_after(response)
                self._backoff(attempt, url, reason=str(response.status_code),
                              override=retry_after)
                last_error = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}", request=response.request,
                    response=response,
                )
                continue

            response.raise_for_status()
            log.debug("http_ok", url=url, source=source_slug,
                      status=response.status_code, bytes=len(response.content))
            return response

        assert last_error is not None
        raise last_error

    def _backoff(self, attempt: int, url: str, *, reason: str,
                 override: float | None = None) -> None:
        delay = override if override is not None else min(2.0**attempt, 30.0)
        log.warning("http_backoff", url=url, attempt=attempt + 1,
                    reason=reason, sleep_s=round(delay, 2))
        time.sleep(delay)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class RobotsDisallowed(RuntimeError):
    """`robots.txt` erişimi yasaklıyor."""


def _parse_retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return min(float(raw), 120.0)
    except ValueError:
        return None
