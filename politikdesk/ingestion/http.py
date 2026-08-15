"""Kibarlık (politeness) katmanı (F1-07).

DoD: kaynak başına dakikada azami istek sınırı uygulanıyor; 429/503'te
üstel geri çekilme.

Spec §9.3 madde 4: toplu izinsiz scraping hiçbir fazda kullanılmaz.
Bu katman "izinli erişimi kibarca yap"manın aracıdır — hız kazanmanın
değil.
"""

from __future__ import annotations

import contextlib
import os
import ssl
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import certifi
import httpx

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
NON_RETRYABLE_ERRORS = (
    httpx.UnsupportedProtocol,
    httpx.DecodingError,
    httpx.InvalidURL,
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
    """certifi demeti + `certs/` altındaki ara sertifikalar.

    Bazı sunucular ara sertifikayı göndermez. Tarayıcılar eksik halkayı
    AIA adresinden kendileri indirir (*AIA chasing*); Python'un `ssl`
    modülü indirmez ve doğrulama düşer. Sonuç, teşhisi zor bir
    asimetridir: **site tarayıcıda açılır, koddan açılmaz.**
    (Ölçülen örnek: `resmigazete.gov.tr` — yaprak sertifika DigiCert
    imzalı ve geçerli, ama `GeoTrust TLS RSA CA G1` halkası eksik.)

    Doğrulamayı kapatmak yerine halkayı tamamlıyoruz: Tier 1 birincil
    kaynaktan okuduğumuzu söylerken karşı tarafın gerçekten o kurum
    olduğunu doğrulamamak, kanıt zincirinin kendisini çürütürdü.

    Demet bir kez kurulur ve süreç boyunca yeniden kullanılır.

    Dosya kullanıcıya özel bir dizine yazılır (D04 düzeltmesi): genel
    temp dizini tahmin edilebilir ve çok kullanıcılı ortamda bir saldırgan
    demeti kendi kök CA'sıyla değiştirebilirdi.
    """
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
    parts = [Path(certifi.where()).read_text(encoding="ascii")]
    parts.extend(p.read_text(encoding="ascii") for p in extras)
    bundle.write_text("\n".join(parts), encoding="ascii")
    with contextlib.suppress(OSError):
        os.chmod(bundle, 0o600)
    log.debug("ca_bundle_built", extra_certs=[p.name for p in extras], path=str(bundle))
    return str(bundle)


@lru_cache(maxsize=1)
def ssl_context() -> ssl.SSLContext:
    """Tamamlanmış demetle kurulmuş TLS bağlamı.

    httpx `verify=<dosya yolu>` biçimini kaldırdı (DeprecationWarning) ve
    bir `SSLContext` istiyor. Bağlam bir kez kurulup yeniden kullanılır —
    her istemci için sertifika demetini yeniden ayrıştırmak pahalıdır.
    """
    return ssl.create_default_context(cafile=ca_bundle_path())


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

    def __init__(self, client: httpx.Client, ttl_seconds: float = 86400.0) -> None:
        self._client = client
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, RobotFileParser | None]] = {}
        self._lock = threading.Lock()

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

    def __post_init__(self) -> None:
        accept_hdr = (
            "application/rss+xml, application/xml, text/xml, "
            "text/html;q=0.9, */*;q=0.8"
        )
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


        self._client = httpx.Client(
            headers=base_headers,
            timeout=client_timeout,
            follow_redirects=True,
            http2=False,
            # Eksik ara sertifikaları tamamlanmış demet (F5-20).
            # Doğrulama AÇIK kalır; `verify=False` kullanılmaz.
            verify=ssl_context(),
        )
        self._limiter = RateLimiter(self.max_per_minute)
        self._robots = RobotsCache(self._client) if self.respect_robots else None

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        source_slug: str = "",
    ) -> httpx.Response:
        """Kibarca GET. 429/503'te üstel geri çekilme ile yeniden dener.

        `headers` kimlik doğrulama isteyen uçlar içindir (TÜİK SDMX
        `Authorization: Bearer ...` bekler, F5-02).
        """
        if self.respect_robots and self._robots and not self._robots.allowed(url):
            raise RobotsDisallowed(f"robots.txt bu yolu yasaklıyor: {url}")

        return self._send("GET", url, headers=headers, source_slug=source_slug)

    def post(
        self,
        url: str,
        *,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        source_slug: str = "",
    ) -> httpx.Response:
        """Kibarca POST — kimlik doğrulama uçları için (F5-02).

        `robots.txt` DENETLENMEZ ve bu bilinçlidir: robots bir tarama
        (crawl) sözleşmesidir, kimliğimizle çağırdığımız bir API ucunu
        kapsamaz. Oran sınırı ve geri çekilme aynen uygulanır.
        """
        return self._send("POST", url, data=data, headers=headers,
                          source_slug=source_slug)

    def _send(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        source_slug: str = "",
    ) -> httpx.Response:
        """Ortak gövde: oran sınırı + üstel geri çekilme + yeniden deneme.

        TLS el sıkışması ORTASINDA düşen sunucular var (TÜİK'in
        `nsiws`/`giris` konakları aralıklı olarak
        `UNEXPECTED_EOF_WHILE_READING` veriyor). Bu bir `httpx.HTTPError`
        alt sınıfıdır ve zaten yeniden denenir — tek koşumda "kaynak
        ölü" diye karar vermek yanlış olurdu.
        """
        host = urlparse(url).netloc
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            self._limiter.acquire(host)
            try:
                response = self._client.request(
                    method, url, data=data, headers=headers
                )
            except NON_RETRYABLE_ERRORS as exc:
                # Kurtarılamaz hata (ör. geçersiz URL, protokol): yeniden deneme yapma
                raise exc

            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    self._backoff(attempt, url, reason=type(exc).__name__)
                continue

            if response.status_code in RETRYABLE_STATUS:
                last_error = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}", request=response.request,
                    response=response,
                )
                if attempt < self.max_retries - 1:
                    retry_after = _parse_retry_after(response)
                    self._backoff(attempt, url, reason=str(response.status_code),
                                  override=retry_after)
                continue

            response.raise_for_status()
            log.debug("http_ok", url=url, source=source_slug,
                      status=response.status_code, bytes=len(response.content))
            return response

        assert last_error is not None
        raise last_error

    def _backoff(self, attempt: int, url: str, *, reason: str,
                 override: float | None = None) -> float:
        delay = calculate_backoff(
            attempt,
            jitter=self.enable_jitter,
            override=override,
        )
        log.warning("http_backoff", url=url, attempt=attempt + 1,
                    reason=reason, sleep_s=round(delay, 2))
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
