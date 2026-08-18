"""Beklenen gelişmeler takvimi aracı (F2-18, F2-19).

python -m scripts.calendar_tool load config/calendar_2026.yml
python -m scripts.calendar_tool list
python -m scripts.calendar_tool match
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import yaml

from politikdesk.context.scheduler_match import (
    add_scheduled,
    list_scheduled,
    match_pending,
)
from politikdesk.observability import configure_logging


def cmd_load(path: Path) -> int:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    vertical = data.get("vertical", "macro_economy")

    existing = {(r["title"], str(r["expected_at"])) for r in list_scheduled(limit=1000)}

    added = skipped = 0
    for item in data.get("events", []):
        expected_at = item["expected_at"]
        if isinstance(expected_at, str):
            expected_at = datetime.fromisoformat(expected_at)
        if (item["title"], str(expected_at)) in existing:
            skipped += 1
            continue
        add_scheduled(
            title=item["title"],
            expected_at=expected_at,
            source_slug=item.get("source"),
            vertical=item.get("vertical", vertical),
        )
        added += 1

    unverified = sum(1 for i in data.get("events", []) if not i.get("verified"))
    print(f"Takvim yuklendi: {added} eklendi, {skipped} zaten vardi.")
    if unverified:
        print(f"UYARI: {unverified} kayit 'verified: false' — resmi takvimden teyit edin.")
    return 0


def cmd_list() -> int:
    rows = list_scheduled(limit=200)
    if not rows:
        print("Takvim bos.")
        return 0
    print(f"{'beklenen':17s} {'kaynak':8s} {'durum':9s} baslik")
    for r in rows:
        print(
            f"{str(r['expected_at'])[:16]:17s} "
            f"{(r['source_slug'] or '-'):8s} {r['status']:9s} {r['title'][:60]}"
        )
    return 0


def cmd_match() -> int:
    stats = match_pending()
    print(f"Eslestirme: {stats['matched']}/{stats['pending']} bekleyen kayit eslesti.")
    return 0


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="PolitikDesk takvim araci")
    sub = parser.add_subparsers(dest="command", required=True)

    load = sub.add_parser("load", help="YAML takvimini yukle")
    load.add_argument("path", type=Path)
    sub.add_parser("list", help="Takvimi listele")
    sub.add_parser("match", help="Beklenen gelismeleri olaylarla eslestir")

    args = parser.parse_args()
    if args.command == "load":
        return cmd_load(args.path)
    if args.command == "list":
        return cmd_list()
    if args.command == "match":
        return cmd_match()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
