"""PolitikDesk — Gerçek Kaynak Sağlık ve Canlı Ingestion Denetim Aracı (Faz 24).

101 kaynağın tamamını veya seçilen alt kümelerini tarar; HTTP durumu,
ayrıştırma başarısı, dönen makale sayısı, yanıt süresi (latency) ve
boş feed (200 OK ama 0 item) anomalilerini ölçer.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from typing import Any

from politikdesk.ingestion.sources import load_all_configs


@dataclass
class SourceAuditResult:
    slug: str
    name: str
    kind: str
    adapter: str
    vertical: str
    feed_url: str
    http_status: int | None
    latency_ms: float
    items_count: int
    status: str  # 'HEALTHY', 'EMPTY_FEED', 'HTTP_ERROR', 'TIMEOUT', 'DISABLED', 'CUSTOM_ADAPTER'
    error_message: str | None = None


def audit_rss_source(config: Any, timeout: float = 8.0) -> SourceAuditResult:
    """Tek bir RSS/Atom kaynağını üretim RssAdapter'ı ile canlı olarak sorgular ve ölçer."""
    from politikdesk.ingestion.adapters.rss import RssAdapter
    from politikdesk.ingestion.http import HttpClient

    feed_url = config.feed_url or config.base_url or ""
    if not feed_url:
        return SourceAuditResult(
            slug=config.slug,
            name=config.name,
            kind=config.kind,
            adapter=config.adapter,
            vertical=config.vertical,
            feed_url="",
            http_status=None,
            latency_ms=0.0,
            items_count=0,
            status="NO_URL",
            error_message="Feed URL tanımlı değil",
        )

    if not config.is_ingestable:
        return SourceAuditResult(
            slug=config.slug,
            name=config.name,
            kind=config.kind,
            adapter=config.adapter,
            vertical=config.vertical,
            feed_url=feed_url,
            http_status=None,
            latency_ms=0.0,
            items_count=0,
            status="DISABLED",
            error_message="Kaynak devre dışı veya ToS restricted",
        )

    start_t = time.perf_counter()
    http_client = HttpClient(timeout=timeout)
    adapter = RssAdapter(
        slug=config.slug,
        feed_url=feed_url,
        base_url=config.base_url or "",
        extra_feeds=config.extra_feeds,
        http=http_client,
        keyword_filter=config.keyword_filter,
    )

    try:
        items = adapter.fetch()
        latency = (time.perf_counter() - start_t) * 1000.0
        item_count = len(items)

        if item_count == 0:
            return SourceAuditResult(
                slug=config.slug,
                name=config.name,
                kind=config.kind,
                adapter=config.adapter,
                vertical=config.vertical,
                feed_url=feed_url,
                http_status=200,
                latency_ms=round(latency, 2),
                items_count=0,
                status="EMPTY_FEED",
                error_message="200 OK döndü ancak 0 öğe ayrıştırıldı",
            )

        return SourceAuditResult(
            slug=config.slug,
            name=config.name,
            kind=config.kind,
            adapter=config.adapter,
            vertical=config.vertical,
            feed_url=feed_url,
            http_status=200,
            latency_ms=round(latency, 2),
            items_count=item_count,
            status="HEALTHY",
            error_message=None,
        )

    except Exception as exc:
        latency = (time.perf_counter() - start_t) * 1000.0
        err_str = str(exc)[:100]
        status_name = "TIMEOUT" if "timeout" in err_str.lower() else "NETWORK_ERROR"
        return SourceAuditResult(
            slug=config.slug,
            name=config.name,
            kind=config.kind,
            adapter=config.adapter,
            vertical=config.vertical,
            feed_url=feed_url,
            http_status=None,
            latency_ms=round(latency, 2),
            items_count=0,
            status=status_name,
            error_message=err_str,
        )


def run_sources_audit(sample_limit: int | None = None) -> list[SourceAuditResult]:
    """Tüm yapılandırılmış kaynakları denetler."""
    configs = load_all_configs()
    results: list[SourceAuditResult] = []

    rss_configs = [c for c in configs if c.adapter == "rss"]
    other_configs = [c for c in configs if c.adapter != "rss"]

    target_rss = rss_configs[:sample_limit] if sample_limit else rss_configs

    print(f"[*] Toplam {len(configs)} kaynak tespit edildi.")
    print(f"[*] {len(target_rss)} adet RSS kaynağı canlı taranıyor...")

    for i, cfg in enumerate(target_rss, 1):
        res = audit_rss_source(cfg)
        results.append(res)
        if res.status == "HEALTHY":
            status_tag = "[OK]  "
        elif res.status == "EMPTY_FEED":
            status_tag = "[WARN]"
        else:
            status_tag = "[FAIL]"
        print(
            f"  [{i:02d}/{len(target_rss):02d}] {status_tag} {res.slug:<18} | "
            f"{res.status:<12} | Latency: {res.latency_ms:>6.1f}ms | "
            f"Items: {res.items_count:>3d} | {res.name}"
        )

    # Özel adaptörleri kaydet
    for cfg in other_configs:
        results.append(
            SourceAuditResult(
                slug=cfg.slug,
                name=cfg.name,
                kind=cfg.kind,
                adapter=cfg.adapter,
                vertical=cfg.vertical,
                feed_url=cfg.feed_url or cfg.base_url or "",
                http_status=None,
                latency_ms=0.0,
                items_count=0,
                status="SPECIALIZED_ADAPTER" if cfg.adapter != "twitter" else "TWITTER_BRIDGE",
                error_message=f"{cfg.adapter} özel adaptörü ile çalışır",
            )
        )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="PolitikDesk Kaynak Sağlık Denetim Aracı")
    parser.add_argument("--limit", type=int, default=None, help="Taranacak RSS kaynağı sınırı")
    args = parser.parse_args()

    results = run_sources_audit(sample_limit=args.limit)

    healthy = [r for r in results if r.status == "HEALTHY"]
    empty = [r for r in results if r.status == "EMPTY_FEED"]
    errors = [r for r in results if r.status in ("HTTP_ERROR", "TIMEOUT", "NETWORK_ERROR")]
    specialized = [r for r in results if r.status in ("SPECIALIZED_ADAPTER", "TWITTER_BRIDGE")]

    print("\n" + "=" * 70)
    print("POLİTİKDESK KAYNAK SAĞLIK MATRİSİ ÖZETİ")
    print("=" * 70)
    print(f"Toplam Kaynak:        {len(results)}")
    print(f"Sağlıklı RSS (Aktif): {len(healthy)} (Öğe çeken ve ayrıştırılan)")
    print(f"Boş RSS Feed:         {len(empty)} (200 OK ama 0 öğe)")
    print(f"Hata Alan Kaynaklar:  {len(errors)}")
    print(f"Özel Adaptörler:      {len(specialized)} (Resmi kurum API'leri & Twitter)")
    print("=" * 70)


if __name__ == "__main__":
    main()
