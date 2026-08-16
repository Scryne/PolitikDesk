"""Tüm Dikey Kaynakları İçin RSS / Feed Canlılık Doğrulayıcı (Spec v3.5 §9.2).

Kullanım:
    python -m scripts.verify_feeds [--file config/sources_legislation.yml] [--timeout 15] [--strict]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from xml.etree import ElementTree

# Windows konsolunda UTF-8 / cp1254 kodlama hatalarını önle
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from politikdesk.ingestion.http import HttpClient
from politikdesk.ingestion.sources import load_all_configs, load_config

REPO_ROOT = Path(__file__).resolve().parent.parent


def verify_all_feeds(
    config_file: str | None = None,
    timeout: float = 15.0,
    strict: bool = False,
) -> int:
    print("=" * 85)
    print("PolitikDesk — RSS ve Feed Canlilik / Saglik Denetimi")
    print("=" * 85)

    if config_file:
        cfg_path = REPO_ROOT / config_file
        configs, _ = load_config(cfg_path)
    else:
        configs = load_all_configs(REPO_ROOT / "config")

    http = HttpClient(timeout=timeout)
    results: list[dict[str, object]] = []
    has_failure = False

    feed_configs = [
        c for c in configs if c.feed_url and c.access_method in ("rss", "official_feed")
    ]

    print(f"Denetlenecek Feed Sayisi: {len(feed_configs)}\n")
    print(f"{'SLUG':<22} {'DURUM':<10} {'KOD':<6} {'OGE':<6} {'SURE':<8} {'FEED URL'}")
    print("-" * 85)

    for cfg in feed_configs:
        feed_url = cfg.feed_url
        if not feed_url:
            continue

        started = time.perf_counter()
        status_code: int | str = "ERR"
        item_count = 0
        status_label = "[FAIL]"
        detail = ""

        try:
            resp = http.get(feed_url, source_slug=cfg.slug)
            status_code = resp.status_code
            elapsed_ms = int((time.perf_counter() - started) * 1000)

            if resp.status_code == 200:
                try:
                    root = ElementTree.fromstring(resp.text)
                    items = root.findall(".//item") or root.findall(
                        ".//{http://www.w3.org/2005/Atom}entry"
                    )
                    item_count = len(items)
                    if item_count > 0:
                        status_label = "[OK]"
                    else:
                        status_label = "[BOS]"
                        detail = "0 öğe döndü"
                except Exception as exc:
                    status_label = "[PARSE]"
                    detail = f"XML parse hatası: {str(exc)[:50]}"
            else:
                detail = f"HTTP {resp.status_code}"
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            detail = f"{type(exc).__name__}: {str(exc)[:60]}"

        if status_label != "[OK]":
            has_failure = True

        print(
            f"{cfg.slug:<22} {status_label:<10} {str(status_code):<6} "
            f"{item_count:<6} {f'{elapsed_ms}ms':<8} {feed_url[:40]}"
        )
        if detail:
            print(f"   └─ Detay: {detail}")

        results.append(
            {
                "slug": cfg.slug,
                "status": status_label,
                "status_code": status_code,
                "items": item_count,
                "detail": detail,
            }
        )

    print("-" * 85)
    ok_count = sum(1 for r in results if r["status"] == "[OK]")
    print(f"Sonuc: {ok_count} / {len(feed_configs)} feed saglikli ve erisilebilir.")
    print("=" * 85)

    if has_failure and strict:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="RSS feed canlilik dogrulamasi")
    parser.add_argument(
        "--file", type=str, default=None, help="Belirli bir config/sources*.yml dosyasi"
    )
    parser.add_argument("--timeout", type=float, default=15.0, help="Zaman asimi (saniye)")
    parser.add_argument(
        "--strict", action="store_true", help="Herhangi bir hata durumunda cikis kodu 1 don"
    )
    args = parser.parse_args()

    return verify_all_feeds(config_file=args.file, timeout=args.timeout, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
