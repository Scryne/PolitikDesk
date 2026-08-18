"""Kibarlık (politeness) katmanı (F1-07).

DoD: kaynak başına dakikada azami istek sınırı uygulanıyor; 429/503'te
üstel geri çekilme.

Spec §9.3 madde 4: toplu izinsiz scraping hiçbir fazda kullanılmaz.
Bu katman "izinli erişimi kibarca yap"manın aracıdır — hız kazanmanın
değil.
"""

from __future__ import annotations

import contextlib
import ipaddress
import os
import socket
import ssl
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import certifi
import httpx

from politikdesk.ingestion.circuit import CircuitOpenError, get_circuit
from politikdesk.observability import get_logger

log = get_logger(__name__)

USER_AGENT = (
    "PolitikDeskBot/0.1 (+kisisel arastirma araci; "
    "kaynak gostererek alinti yapar; iletisim: repo sahibi)"
)
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 20.0
DEFAULT_CONNECT_TIMEOUT = 10.0
DEFAULT_READ_TIMEOUT = 15.0
DEFAULT_WRITE_TIMEOUT = 10.0
DEFAULT_POOL_TIMEOUT = 5.0
DEFAULT_MAX_RETRIES = 4
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_DISALLOWED_HOSTNAMES = frozenset({
    "localhost",
    "localhost.localdomain",
    "0.0.0.0",
    "127.0.0.1",
    "::1",
})
_DISALLOWED_SUFFIXES = (
    ".local",
    ".internal",
    ".corp",
    ".lan",
    ".home",
    ".intranet",
)


class UnsafeUrlError(ValueError):
    """URL güvenli değil (iç ağ, desteklenmeyen şema, çözülemeyen host, geçersiz format)."""


def _is_private(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return _is_private(ip.ipv4_mapped)
    return False


def validate_url(url: str, *, resolve_dns: bool = True) -> str:
    """SSRF koruması: yalnızca genel internet adreslerine izin verir."""
    if not url or not isinstance(url, str):
        raise UnsafeUrlError("Geçersiz veya boş URL")

    url_str = url.strip()
    try:
        parsed = urlparse(url_str)
    except Exception as exc:
        raise UnsafeUrlError(f"Ayrıştırılamayan URL: {url_str}") from exc

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"Desteklenmeyen şema: {parsed.scheme!r}")
    if not parsed.hostname:
        raise UnsafeUrlError("URL'de host yok")

    host = parsed.hostname.lower().strip("[]").rstrip(".")
    if (
        host in _DISALLOWED_HOSTNAMES
        or any(host.endswith(suffix) for suffix in _DISALLOWED_SUFFIXES)
    ):
        raise UnsafeUrlError(f"Yerel/özel adrese erişilemez: {host}")

    # Doğrudan IP verilmişse (IPv4, IPv6 veya ondalık integer IP)
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None = None
    try:
        ip = (
            ipaddress.IPv4Address(int(host))
            if host.isdigit()
            else ipaddress.ip_address(host)
        )
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
                raise UnsafeUrlError(f"Host özel bir adrese çözümleniyor: {host} -> {resolved}")

    return url_str


NON_RETRYABLE_ERRORS = (
    httpx.UnsupportedProtocol,
    httpx.DecodingError,
    httpx.InvalidURL,
    UnsafeUrlError,
    CircuitOpenError,
)


def calculate_backoff(
    attempt: int,
    base: float = 1.0,
    max_delay: float = 30.0,
    *,
    jitter: bool = False,
    override: float | None = None,
) -> float:
    """Üstel geri çekilme süresini hesaplar (F1-07, F4).

    Jitter etkinse retry storm'ları engellemek için gecikmeye rastgelelik ekler.
    `override` (ör. Retry-After) verilmişse doğrudan kullanılır.
    """
    if override is not None:
        return override
    exp_delay = min(base * (2.0**attempt), max_delay)
    if jitter:
        import random

        return random.uniform(0.5 * exp_delay, exp_delay)
    return exp_delay


# Sunucunun göndermeyi unuttuğu ARA sertifikalar (F5-20). Kök değildir;
# güven sınırını genişletmez — gerekçe `certs/README.md`.
CERTS_DIR = Path(__file__).resolve().parent.parent.parent / "certs"


@lru_cache(maxsize=1)
def ca_bundle_path() -> str:
    """certifi demeti + `certs/` altındaki ara sertifikalar."""
    extras = sorted(CERTS_DIR.glob("*.pem")) if CERTS_DIR.is_dir() else []
    if not extras:
        return certifi.where()

    # Kullanıcıya özel dizin: Windows'ta LOCALAPPDATA, Linux'ta ~/.cache.
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        cache_dir = Path(base) / "PolitikDesk" / "cache"
    else:
        xdg = os.environ.get("XDG_CACHE_HOME")
        cache_dir = Path(xdg) if xdg else Path.home() / ".cache" / "politikdesk"

    cache_dir.mkdir(parents=True, exist_ok=True)
    bundle = cache_dir / "ca-bundle.pem"
    temp_bundle = cache_dir / "ca-bundle.pem.tmp"
    parts = [Path(certifi.where()).read_text(encoding="ascii")]
    parts.extend(p.read_text(encoding="ascii") for p in extras)

    temp_bundle.write_text("\n".join(parts), encoding="ascii")
    with contextlib.suppress(OSError):
        os.chmod(temp_bundle, 0o600)
    temp_bundle.replace(bundle)
    log.debug("ca_bundle_built", extra_certs=[p.name for p in extras], path=str(bundle))
    return str(bundle)


@lru_cache(maxsize=1)
def ssl_context() -> ssl.SSLContext:
    """Tamamlanmış demetle kurulmuş TLS bağlamı."""
    return ssl.create_default_context(cafile=ca_bundle_path())


def get_redis_client() -> Any | None:
    """Redis istemcisini yapılandırır veya None döner."""
    try:
        from politikdesk.config import get_settings

        settings = get_settings()
        if not settings.redis_url:
            return None
        import redis

        return redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=2.0)
    except Exception:
        return None


_REDIS_RATELIMIT_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local member = ARGV[3]
local window = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)

if count < limit then
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, ttl)
    return {1, 0}
else
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local oldest_ts = now - window
    if oldest and #oldest >= 2 then
        oldest_ts = tonumber(oldest[2])
    end
    local wait_time = math.max(0.01, window - (now - oldest_ts) + 0.01)
    return {0, wait_time}
end
"""


class RateLimiter:
    """Kaynak (host) başına dakikada azami istek sayısı (in-memory veya Redis koordineli)."""

    def __init__(self, max_per_minute: int = 12, redis_client: Any | None = None) -> None:
        self.max_per_minute = max_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._redis = redis_client

    def acquire(self, key: str) -> float:
        """Gerekirse bekler. Beklenen saniyeyi döndürür."""
        if self._redis is not None:
            return self._acquire_redis(key)
        return self._acquire_memory(key)

    def _acquire_memory(self, key: str) -> float:
        waited = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                window = self._hits[key]
                while window and now - window[0] > 60.0:
                    window.popleft()
                if len(window) < self.max_per_minute:
                    window.append(now)
                    self._cleanup_expired(now, exclude_key=key)
                    return waited
                sleep_for = 60.0 - (now - window[0]) + 0.01
            time.sleep(sleep_for)
            waited += sleep_for

    def _cleanup_expired(self, now: float, exclude_key: str | None = None) -> None:
        """Süresi dolmuş/boş pencereye sahip host anahtarlarını temizler (IMP-05)."""
        expired_keys = [
            k
            for k, win in self._hits.items()
            if k != exclude_key and (not win or now - win[-1] > 60.0)
        ]
        for k in expired_keys:
            del self._hits[k]

    def _acquire_redis(self, key: str) -> float:
        if self._redis is None:
            return self._acquire_memory(key)
        waited = 0.0
        redis_key = f"pd:ratelimit:{key}"
        while True:
            try:
                now = time.time()
                member = f"{now}_{time.monotonic()}"
                result = self._redis.eval(
                    _REDIS_RATELIMIT_LUA,
                    1,
                    redis_key,
                    str(now),
                    str(self.max_per_minute),
                    member,
                    "60.0",
                    "65",
                )
                allowed = int(result[0])
                wait_time = float(result[1])

                if allowed == 1:
                    return waited

                time.sleep(wait_time)
                waited += wait_time
            except Exception as exc:
                log.warning("redis_ratelimit_failed_fallback_inmemory", error=str(exc)[:100])
                return self._acquire_memory(key)


class RobotsCache:
    """`robots.txt` saygısı. In-memory veya Redis koordineli."""

    def __init__(
        self,
        client: httpx.Client,
        ttl_seconds: float = 86400.0,
        redis_client: Any | None = None,
    ) -> None:
        self._client = client
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, RobotFileParser | None]] = {}
        self._lock = threading.Lock()
        self._redis = redis_client

    def allowed(self, url: str, user_agent: str = USER_AGENT) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        now = time.monotonic()

        with self._lock:
            cached = self._cache.get(origin)
            if cached is None or (now - cached[0] > self._ttl):
                parser = self._load(origin)
                self._cache[origin] = (now, parser)
            else:
                parser = cached[1]

        if parser is None:
            return True
        return parser.can_fetch(user_agent, url)

    def _load(self, origin: str) -> RobotFileParser | None:
        if self._redis is not None:
            try:
                cached_text = self._redis.get(f"pd:robots:{origin}")
                if cached_text is not None:
                    if cached_text == "__NOT_FOUND__":
                        return None
                    parser = RobotFileParser()
                    parser.parse(cached_text.splitlines())
                    return parser
            except Exception as exc:
                log.debug("redis_robots_cache_get_failed", error=str(exc)[:100])

        try:
            response = self._client.get(f"{origin}/robots.txt", timeout=10.0)
            if response.status_code != 200:
                log.info("robots_not_published", origin=origin, status=response.status_code)
                if self._redis is not None:
                    with contextlib.suppress(Exception):
                        self._redis.setex(f"pd:robots:{origin}", int(self._ttl), "__NOT_FOUND__")
                return None
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
            if self._redis is not None:
                with contextlib.suppress(Exception):
                    self._redis.setex(f"pd:robots:{origin}", int(self._ttl), response.text)
            return parser
        except Exception:  # noqa: BLE001
            log.info("robots_fetch_failed", origin=origin)
            return None


@dataclass
class HttpClient:
    """Kibar HTTP istemcisi: UA, oran sınırı, robots, üstel geri çekilme, SSRF koruması."""

    max_per_minute: int = 12
    timeout: float | httpx.Timeout = DEFAULT_TIMEOUT
    connect_timeout: float | None = None
    read_timeout: float | None = None
    write_timeout: float | None = None
    pool_timeout: float | None = None
    max_retries: int = DEFAULT_MAX_RETRIES
    respect_robots: bool = True
    user_agent: str = USER_AGENT
    custom_headers: dict[str, str] | None = None
    enable_jitter: bool = False
    enforce_ssrf: bool = True
    resolve_dns: bool = True
    redis_client: Any | None = None
    use_redis: bool = False

    def __post_init__(self) -> None:
        accept_hdr = "application/rss+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8"
        base_headers = {
            "User-Agent": self.user_agent,
            "Accept": accept_hdr,
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
        }
        if self.custom_headers:
            base_headers.update(self.custom_headers)

        if isinstance(self.timeout, httpx.Timeout):
            client_timeout = self.timeout
        elif any(
            v is not None
            for v in (
                self.connect_timeout,
                self.read_timeout,
                self.write_timeout,
                self.pool_timeout,
            )
        ):
            client_timeout = httpx.Timeout(
                timeout=self.timeout,
                connect=self.connect_timeout,
                read=self.read_timeout,
                write=self.write_timeout,
                pool=self.pool_timeout,
            )
        else:
            client_timeout = httpx.Timeout(self.timeout)

        effective_redis = (
            self.redis_client if self.redis_client is not None
            else (get_redis_client() if self.use_redis else None)
        )

        def _on_request(request: httpx.Request) -> None:
            if self.enforce_ssrf:
                validate_url(str(request.url), resolve_dns=self.resolve_dns)

        self._client = httpx.Client(
            headers=base_headers,
            timeout=client_timeout,
            follow_redirects=True,
            http2=False,
            event_hooks={"request": [_on_request]},
            verify=ssl_context(),
        )
        self._limiter = RateLimiter(self.max_per_minute, redis_client=effective_redis)
        self._robots = (
            RobotsCache(self._client, redis_client=effective_redis) if self.respect_robots else None
        )

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        source_slug: str = "",
        follow_redirects: bool | None = None,
    ) -> httpx.Response:
        """Kibarca GET. 429/503'te üstel geri çekilme ile yeniden dener.

        `headers` kimlik doğrulama isteyen uçlar içindir (TÜİK SDMX
        `Authorization: Bearer ...` bekler, F5-02).
        """
        if self.respect_robots and self._robots and not self._robots.allowed(url):
            raise RobotsDisallowed(f"robots.txt bu yolu yasaklıyor: {url}")

        return self._send(
            "GET",
            url,
            headers=headers,
            source_slug=source_slug,
            follow_redirects=follow_redirects,
        )

    def post(
        self,
        url: str,
        *,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        source_slug: str = "",
        follow_redirects: bool | None = None,
    ) -> httpx.Response:
        """Kibarca POST — kimlik doğrulama uçları için (F5-02).

        `robots.txt` DENETLENMEZ ve bu bilinçlidir: robots bir tarama
        (crawl) sözleşmesidir, kimliğimizle çağırdığımız bir API ucunu
        kapsamaz. Oran sınırı ve geri çekilme aynen uygulanır.
        """
        return self._send(
            "POST",
            url,
            data=data,
            headers=headers,
            source_slug=source_slug,
            follow_redirects=follow_redirects,
        )

    def _send(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        source_slug: str = "",
        follow_redirects: bool | None = None,
    ) -> httpx.Response:
        """Ortak gövde: oran sınırı + üstel geri çekilme + yeniden deneme.

        TLS el sıkışması ORTASINDA düşen sunucular var (TÜİK'in
        `nsiws`/`giris` konakları aralıklı olarak
        `UNEXPECTED_EOF_WHILE_READING` veriyor). Bu bir `httpx.HTTPError`
        alt sınıfıdır ve zaten yeniden denenir — tek koşumda "kaynak
        ölü" diye karar vermek yanlış olurdu.
        """
        host = urlparse(url).netloc
        circuit = get_circuit(host)
        circuit.check_or_raise()

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            self._limiter.acquire(host)
            try:
                req_kwargs: dict[str, Any] = {"data": data, "headers": headers}
                if follow_redirects is not None:
                    req_kwargs["follow_redirects"] = follow_redirects
                response = self._client.request(method, url, **req_kwargs)
            except NON_RETRYABLE_ERRORS as exc:
                if not isinstance(exc, CircuitOpenError):
                    circuit.record_failure(error=type(exc).__name__)
                # Kurtarılamaz hata (ör. geçersiz URL, protokol): yeniden deneme yapma
                raise exc

            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    self._backoff(attempt, url, reason=type(exc).__name__)
                continue

            if response.status_code in RETRYABLE_STATUS:
                last_error = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )
                if attempt < self.max_retries - 1:
                    retry_after = _parse_retry_after(response)
                    self._backoff(
                        attempt, url, reason=str(response.status_code), override=retry_after
                    )
                continue

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                circuit.record_failure(error=f"HTTP {response.status_code}")
                raise exc

            circuit.record_success()
            log.debug(
                "http_ok",
                url=url,
                source=source_slug,
                status=response.status_code,
                bytes=len(response.content),
            )
            return response

        assert last_error is not None
        circuit.record_failure(error=type(last_error).__name__)
        raise last_error

    def _backoff(
        self, attempt: int, url: str, *, reason: str, override: float | None = None
    ) -> float:
        delay = calculate_backoff(
            attempt,
            jitter=self.enable_jitter,
            override=override,
        )
        log.warning(
            "http_backoff", url=url, attempt=attempt + 1, reason=reason, sleep_s=round(delay, 2)
        )
        time.sleep(delay)
        return delay

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
