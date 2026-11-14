"""İki bağımsız etiketleyicinin CSV'lerini birleştirir; uyuşmazlığı hakeme bırakır.

Kural: bir olay ancak iki etiketleyici **aynı makale kümesini** aynı olay
saydıysa kabul edilir (olay adları farklı olabilir; önemli olan bölümlemedir).
Bölümlemesi uyuşmayan makaleler `anlasmazlik.csv`'ye yazılır; hakem
`hakem_event_id` sütununu doldurur ve betik `--hakem` ile yeniden koşulur.

Çıktı doğrudan altın sete YAZILMAZ: `eval/golden_set_v2_aday.jsonl`'e yazılır,
`label_source: "human_v2"` taşır. Gözden geçirildikten sonra elle eklenir.

    python -m eval.etiketleme.birlestir A.csv B.csv \
        --cikti eval/golden_set_v2_aday.jsonl --anlasmazlik eval/etiketleme/anlasmazlik.csv
    python -m eval.etiketleme.birlestir A.csv B.csv --hakem eval/etiketleme/anlasmazlik.csv ...
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

LABEL_SOURCE = "human_v2"


@dataclass(frozen=True)
class Merge:
    accepted: dict[str, str]  # article_id -> birleşik event_id
    disputed: list[str]  # hakem bekleyen makaleler
    pair_agreement: float  # aynı konudaki çiftlerde "aynı olay mı" kararının uyumu
    pairs: int


def read_labels(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out: dict[str, dict[str, str]] = {}
    for r in rows:
        aid = (r.get("article_id") or "").strip()
        if aid:
            out[aid] = {k: (v or "").strip() for k, v in r.items()}
    return out


def _groups(labels: dict[str, str]) -> dict[str, frozenset[str]]:
    by_event: dict[str, set[str]] = defaultdict(set)
    for aid, evt in labels.items():
        by_event[evt].add(aid)
    return {aid: frozenset(by_event[evt]) for aid, evt in labels.items()}


def merge(a: dict[str, str], b: dict[str, str], topic: dict[str, str]) -> Merge:
    """`a`, `b`: article_id -> event_id (boş etiketli satırlar önceden atılmış)."""
    common = sorted(set(a) & set(b))
    a_c = {k: a[k] for k in common}
    b_c = {k: b[k] for k in common}
    ga, gb = _groups(a_c), _groups(b_c)

    accepted: dict[str, str] = {}
    disputed: list[str] = []
    for aid in common:
        if ga[aid] == gb[aid]:
            # Ortak, kararlı bir olay adı: kümedeki en küçük article_id
            accepted[aid] = "evt-v2-" + min(ga[aid])
        else:
            disputed.append(aid)

    agree = total = 0
    for x, y in combinations(common, 2):
        if topic.get(x) != topic.get(y):
            continue
        total += 1
        agree += (a_c[x] == a_c[y]) == (b_c[x] == b_c[y])
    return Merge(accepted, disputed, agree / total if total else 1.0, total)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="İki etiketleyicinin Golden Set v2 etiketlerini birleştirir"
    )
    ap.add_argument("a", type=Path)
    ap.add_argument("b", type=Path)
    ap.add_argument(
        "--hakem", type=Path, help="hakem_event_id sütunu doldurulmuş anlaşmazlık CSV'si"
    )
    ap.add_argument("--cikti", type=Path, required=True)
    ap.add_argument("--anlasmazlik", type=Path, required=True)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    rows_a, rows_b = read_labels(args.a), read_labels(args.b)
    a = {k: r["event_id"] for k, r in rows_a.items() if r.get("event_id")}
    b = {k: r["event_id"] for k, r in rows_b.items() if r.get("event_id")}
    topic = {k: r.get("topic", "") for k, r in rows_a.items()}
    m = merge(a, b, topic)

    final = dict(m.accepted)
    still_disputed = list(m.disputed)
    if args.hakem and args.hakem.exists():
        hakem = read_labels(args.hakem)
        for aid in m.disputed:
            evt = hakem.get(aid, {}).get("hakem_event_id", "")
            if evt:
                final[aid] = "evt-v2-h-" + evt
        still_disputed = [aid for aid in m.disputed if aid not in final]

    args.anlasmazlik.parent.mkdir(parents=True, exist_ok=True)
    with args.anlasmazlik.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["article_id", "topic", "title", "a_event_id", "b_event_id", "hakem_event_id"])
        for aid in still_disputed:
            w.writerow([aid, topic.get(aid, ""), rows_a[aid].get("title", ""), a[aid], b[aid], ""])

    args.cikti.parent.mkdir(parents=True, exist_ok=True)
    with args.cikti.open("w", encoding="utf-8", newline="\n") as fh:
        for aid in sorted(final):
            r = rows_a[aid]
            hard = "hard" in {r.get("difficulty", ""), rows_b[aid].get("difficulty", "")}
            row = {
                "article_id": aid,
                "event_id": final[aid],
                "title": r.get("title", ""),
                "excerpt": r.get("excerpt", ""),
                "published_at": r.get("published_at", ""),
                "source_slug": r.get("source_slug", ""),
                "url": r.get("url", ""),
                "topic": r.get("topic", ""),
                "difficulty": "hard" if hard else "easy",
                "label_source": LABEL_SOURCE,
                "labelers": [r.get("etiketleyen", ""), rows_b[aid].get("etiketleyen", "")],
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    only_one = sorted(set(a) ^ set(b))
    print(
        f"Ortak etiketli: {len(set(a) & set(b))} · kabul: {len(final)} · "
        f"hakem bekleyen: {len(still_disputed)} · yalnız bir etiketleyicide: {len(only_one)}"
    )
    print(f"Çift uyumu (aynı konu içinde): {m.pair_agreement:.3f} ({m.pairs} çift)")
    if m.pair_agreement < 0.90:
        print("UYARI: uyum 0,90'ın altında; etiket kılavuzunu birlikte gözden geçirin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
