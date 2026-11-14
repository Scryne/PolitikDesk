"""Golden Set v2 (F2-20, 300 makale) için etiketlenecek aday makaleleri seçer.

Etiket ÜRETMEZ. Yalnız insanın etiketleyeceği CSV'yi hazırlar; `event_id`,
`difficulty` ve `etiketleyen` sütunları boş gelir. Etiket insan işidir:
W1 genişletmesinde etiketin insan dışında üretilmesi seti bozmuştu
(`eval/threshold_report.md`, 2026-11-14).

Örnekleme iki şeyi dengeler:

* **Konu kotası.** MVP'nin 10 konusunun her birine eşit pay (Spec §5).
* **Çok makaleli olay.** v1'de olayların yarısı tek makaleliydi ve kümeleme
  ölçümü bu kümelerde anlamsızlaşıyor. Bu yüzden her tohum makalenin yanına,
  72 saat içinde yayımlanmış en yakın komşuları (gömme benzerliği ≥ eşik)
  eklenir. Yakın ama farklı olaylar ("zor küme") da bu yoldan gelir.

Satırlar konu + yayın zamanına göre sıralanır, tohum gruplarına göre değil:
sistemin benzerlik kararı etiketleyene ipucu olarak gösterilmez.

Veritabanına yalnız SELECT atar. Kullanım (proje kökünde):

    python -m eval.etiketleme.orneklem --baslangic 2026-09-01 --bitis 2026-11-30 \
        --hedef 245 --cikti eval/etiketleme/aday.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from eval.golden_set_tools import VALID_TOPICS  # noqa: E402

GOLDEN_V1 = REPO_ROOT / "eval" / "golden_set_v1.jsonl"
COLUMNS = (
    "sira",
    "article_id",
    "source_slug",
    "url",
    "published_at",
    "topic",
    "title",
    "excerpt",
    # Etiketleyenin dolduracağı sütunlar
    "event_id",
    "difficulty",
    "etiketleyen",
    "not",
)


def topic_quotas(target: int, topics: list[str]) -> dict[str, int]:
    """Hedefi konulara olabildiğince eşit böler; artan paylar alfabetik ilk konulara."""
    base, extra = divmod(target, len(topics))
    return {t: base + (1 if i < extra else 0) for i, t in enumerate(sorted(topics))}


def known_titles(path: Path = GOLDEN_V1) -> set[str]:
    if not path.exists():
        return set()
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {r["title"].strip().casefold() for r in rows}


def main_topic(topics: list[str] | None) -> str | None:
    for t in topics or []:
        if t in VALID_TOPICS:
            return t
    return None


def fetch_pool(start: date, end: date) -> list[dict[str, Any]]:
    from politikdesk.db import connection

    with connection() as conn:
        rows = conn.execute(
            """
            SELECT a.id, s.slug AS source_slug, a.canonical_url AS url, a.title,
                   coalesce(a.lead_paragraph, a.excerpt, '') AS excerpt,
                   a.published_at, a.topics
              FROM articles a JOIN sources s ON s.id = a.source_id
             WHERE a.published_at >= %s AND a.published_at < %s
               AND a.embedding IS NOT NULL
               AND a.near_duplicate_of_id IS NULL
             ORDER BY a.id
            """,
            (start, end + timedelta(days=1)),
        ).fetchall()
    return [dict(r) for r in rows]


def neighbours(article_id: int, min_similarity: float, limit: int) -> list[int]:
    from politikdesk.db import connection

    with connection() as conn:
        rows = conn.execute(
            """
            SELECT b.id, 1 - (b.embedding <=> a.embedding) AS sim
              FROM articles a JOIN articles b
                ON b.id <> a.id
               AND b.embedding IS NOT NULL
               AND b.near_duplicate_of_id IS NULL
               AND abs(extract(epoch FROM b.published_at - a.published_at)) <= 72 * 3600
             WHERE a.id = %s
             ORDER BY b.embedding <=> a.embedding
             LIMIT %s
            """,
            (article_id, limit),
        ).fetchall()
    return [int(r["id"]) for r in rows if float(r["sim"]) >= min_similarity]


def select(
    pool: list[dict[str, Any]],
    quotas: dict[str, int],
    neighbour_fn: Any,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Konu kotasını tohum + komşu gruplarıyla doldurur."""
    by_id = {r["id"]: r for r in pool}
    chosen: dict[int, dict[str, Any]] = {}
    for topic, quota in quotas.items():
        seeds = [r for r in pool if main_topic(r["topics"]) == topic]
        rng.shuffle(seeds)
        taken = 0
        for seed in seeds:
            if taken >= quota:
                break
            if seed["id"] in chosen:
                continue
            group = [seed["id"], *[n for n in neighbour_fn(seed["id"]) if n in by_id]]
            for aid in group:
                if taken >= quota:
                    break
                if aid not in chosen:
                    row = dict(by_id[aid])
                    row["topic"] = main_topic(row["topics"]) or topic
                    chosen[aid] = row
                    taken += 1
    return sorted(chosen.values(), key=lambda r: (r["topic"], r["published_at"]))


def write_csv(rows: list[dict[str, Any]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig: Excel ve LibreOffice Türkçe karakterleri doğru açar
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for i, r in enumerate(rows, 1):
            writer.writerow(
                {
                    "sira": i,
                    "article_id": f"db-{r['id']}",
                    "source_slug": r["source_slug"],
                    "url": r["url"],
                    "published_at": r["published_at"].isoformat(),
                    "topic": r["topic"],
                    "title": r["title"],
                    "excerpt": (r["excerpt"] or "")[:600],
                    "event_id": "",
                    "difficulty": "",
                    "etiketleyen": "",
                    "not": "",
                }
            )


def main(argv: list[str] | None = None) -> int:
    from politikdesk.config import load_env_file

    load_env_file()
    ap = argparse.ArgumentParser(description="Golden Set v2 aday örneklemi (etiket üretmez)")
    ap.add_argument("--baslangic", type=date.fromisoformat, required=True)
    ap.add_argument("--bitis", type=date.fromisoformat, required=True)
    ap.add_argument("--hedef", type=int, default=245, help="300 - mevcut insan etiketli 55")
    ap.add_argument("--cikti", type=Path, required=True)
    ap.add_argument("--tohum", type=int, default=20261114)
    ap.add_argument("--komsu-esik", type=float, default=0.80)
    ap.add_argument("--komsu-sayisi", type=int, default=4)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    seen = known_titles()
    pool = [
        r
        for r in fetch_pool(args.baslangic, args.bitis)
        if r["title"].strip().casefold() not in seen
    ]
    present = sorted({t for r in pool if (t := main_topic(r["topics"]))})
    if not present:
        print("Aralıkta MVP konusuna girmiş makale yok.", file=sys.stderr)
        return 1
    quotas = topic_quotas(args.hedef, present)
    rows = select(
        pool,
        quotas,
        lambda aid: neighbours(aid, args.komsu_esik, args.komsu_sayisi),
        random.Random(args.tohum),
    )
    write_csv(rows, args.cikti)
    missing = sorted(set(VALID_TOPICS) - set(present))
    print(f"{len(rows)} aday yazıldı: {args.cikti} (havuz {len(pool)})")
    for t in sorted(quotas):
        n = sum(1 for r in rows if r["topic"] == t)
        print(f"  {t:24s} {n:3d} / {quotas[t]}")
    if missing:
        print(f"Aralıkta hiç makalesi olmayan konular: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
