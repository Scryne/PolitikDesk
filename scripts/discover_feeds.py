"""Akış keşif aracı (F0-08 tamamlayıcısı).

`config/sources.yml` içinde `verified: false` olan kaynakların akış
uçlarını arar. Aday URL'leri dener, RSS otomatik keşfini (`<link
rel="alternate">`) okur ve çalışanları raporlar.

Neden ayrı bir araç: bazı kurum siteleri sandbox/proxy ortamlarından
farklı davranır (JS ile yükleme, UA filtresi, bağlantı sıfırlama).
Bu araç **yerel ağdan** koşturulduğunda gerçek sonucu verir.

Kullanım:
    python -m scripts.discover_feeds              # tüm doğrulanmamış kaynaklar
    python -m scripts.discover_feeds tuik hazine  # yalnızca belirtilenler
    python -m scripts.discover_feeds --all        # doğrulanmışları da test et
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from politikdesk.ingestion.http import HttpClient
from politikdesk.ingestion.sources import SourceConfig, load_config

# RSS otomatik keşif etiketi
_ALTERNATE_RE = re.compile(r'<link[^>]+rel=["\']alternate["\'][^>]*>', re.IGNORECASE)
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
_TYPE_RE = re.compile(r'type=["\']([^"\']+)["\']', re.IGNORECASE)
_FEED_TYPES = ("application/rss+xml", "application/atom+xml", "application/xml")

# Yaygın akış yolları
_COMMON_PATHS = (
    "/rss",
    "/rss.xml",
    "/feed",
    "/feed.xml",
    "/atom.xml",
    "/rss/",
    "/feeds/all.xml",
)


@dataclass
class Probe:
    url: str
    ok: bool
    kind: str  # "rss" | "atom" | "html" | "error"
    item_count: int = 0
    detail: str = ""


def looks_like_feed(text: str) -> tuple[bool, str, int]:
    head = text.lstrip()[:400].lower()
    if "<rss" in head or "<rdf" in head:
        return True, "rss", text.count("<item")
    if "<feed" in head:
        return True, "atom", text.count("<entry")
    return False, "html", 0


def autodiscover(html: str, base_url: str) -> list[str]:
    """Sayfadaki `<link rel="alternate" type="application/rss+xml">` uçları."""
    found: list[str] = []
    for tag in _ALTERNATE_RE.findall(html):
        type_match = _TYPE_RE.search(tag)
        href_match = _HREF_RE.search(tag)
        if not href_match:
            continue
        if type_match and type_match.group(1).lower() not in _FEED_TYPES:
            continue
        found.append(urljoin(base_url, href_match.group(1)))
    return found


def probe(client: HttpClient, url: str) -> Probe:
    try:
        response = client.get(url)
    except Exception as exc:  # noqa: BLE001
        return Probe(url, ok=False, kind="error", detail=f"{type(exc).__name__}: {str(exc)[:120]}")

    is_feed, kind, count = looks_like_feed(response.text)
    return Probe(
        url=str(response.url),
        ok=is_feed and count > 0,
        kind=kind,
        item_count=count,
        detail="" if is_feed else f"HTML döndü ({len(response.text)} bayt)",
    )


def candidate_urls(cfg: SourceConfig) -> list[str]:
    urls: list[str] = []
    if cfg.feed_url:
        urls.append(cfg.feed_url)
    urls.extend(cfg.extra_feeds)

    probe_cfg = cfg.probe or {}
    urls.extend(probe_cfg.get("candidates", []))
    for key in ("bulletin_index", "calendar_url"):
        if probe_cfg.get(key):
            urls.append(probe_cfg[key])

    if cfg.base_url:
        urls.extend(urljoin(cfg.base_url, path) for path in _COMMON_PATHS)

    seen: set[str] = set()
    unique_urls: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)
    return unique_urls


def investigate(client: HttpClient, cfg: SourceConfig) -> list[Probe]:
    results = [probe(client, url) for url in candidate_urls(cfg)]

    # Hiçbiri akış değilse ana sayfada otomatik keşif dene
    if not any(p.ok for p in results) and cfg.base_url:
        try:
            home = client.get(cfg.base_url)
            for discovered in autodiscover(home.text, cfg.base_url):
                results.append(probe(client, discovered))
        except Exception as exc:  # noqa: BLE001
            results.append(
                Probe(
                    cfg.base_url,
                    ok=False,
                    kind="error",
                    detail=f"anasayfa: {type(exc).__name__}: {exc}",
                )
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Kaynak akışı keşif aracı")
    parser.add_argument("slugs", nargs="*", help="Yalnızca bu kaynakları test et")
    parser.add_argument("--all", action="store_true", help="Doğrulanmış kaynakları da test et")
    args = parser.parse_args()

    configs, _ = load_config()
    if args.slugs:
        configs = [c for c in configs if c.slug in set(args.slugs)]
    elif not args.all:
        configs = [c for c in configs if not c.verified]

    if not configs:
        print("Test edilecek kaynak yok. --all ile tümünü deneyin.")
        return 0

    client = HttpClient(max_per_minute=30, respect_robots=False)
    exit_code = 0

    try:
        for cfg in configs:
            print(f"\n=== {cfg.slug} — {cfg.name} ===")
            results = investigate(client, cfg)
            working = [p for p in results if p.ok]

            for p in results:
                mark = "[OK]  " if p.ok else "[--]  "
                extra = f"{p.item_count} oge" if p.ok else p.detail
                print(f"  {mark}{p.url}\n         {p.kind}: {extra}")

            if working:
                best = max(working, key=lambda p: p.item_count)
                print(f'\n  -> ONERI: feed_url: "{best.url}"  ({best.item_count} oge, {best.kind})')
            else:
                exit_code = 1
                print("\n  -> Calisan akis bulunamadi. Secenekler:")
                print("     1) Sayfa JS ile yukleniyorsa taryici ag sekmesinden")
                print("        JSON ucunu bulun ve probe.candidates'a ekleyin")
                print("     2) Kurum akis yayimlamiyorsa generic_html adaptorunu")
                print("        link_pattern ile yapilandirin")
    finally:
        client.close()

    print(
        "\nBulunan akislari config/sources.yml icine yazip "
        "verified: true yapin, sonra `pytest tests/test_sources_config.py`."
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
