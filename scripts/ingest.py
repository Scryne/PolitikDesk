"""Ingestion boru hattını elle çalıştırma aracı.

Celery beat 5 dakikada bir aynı işi yapar (F1-05); bu araç geliştirme,
teşhis ve ilk doldurma (backfill) içindir.

Kullanım:
    python -m scripts.ingest sync            # sources.yml -> veritabanı
    python -m scripts.ingest run             # tüm kaynaklardan bir tur
    python -m scripts.ingest run --source aa-ekonomi
    python -m scripts.ingest embed           # bekleyen makaleleri embed et
    python -m scripts.ingest entities        # varlık çıkar
    python -m scripts.ingest health          # kaynak sağlık raporu
    python -m scripts.ingest purge           # süresi geçmiş gövdeleri sil
"""

from __future__ import annotations

import argparse
import sys

from politikdesk.observability import configure_logging


def cmd_sync() -> int:
    from politikdesk.ingestion.sources import load_config, sync_to_database

    configs, meta = load_config()
    result = sync_to_database(configs)
    print(f"Kaynak yapilandirmasi v{meta.get('version')} senkronize edildi.")
    print(f"  eklenen: {result['inserted']}  guncellenen: {result['updated']}")
    for cfg in configs:
        mark = "OK" if cfg.verified else "??"
        print(f"  [{mark}] {cfg.slug:<14} T{cfg.tier} {cfg.tos_status:<10} "
              f"{cfg.adapter}")
    return 0


def cmd_run(source_slug: str | None, no_scope_filter: bool) -> int:
    from politikdesk.ingestion import repository
    from politikdesk.ingestion.pipeline import Pipeline

    pipeline = Pipeline(enforce_topic_scope=not no_scope_filter)

    if source_slug:
        source = repository.get_source(source_slug)
        if source is None:
            print(f"Kaynak bulunamadi: {source_slug}", file=sys.stderr)
            return 2
        stats = pipeline.run_source(source)
    else:
        stats = pipeline.run_all()

    print("Ingestion turu tamamlandi:")
    print(f"  cekilen         : {stats.fetched}")
    print(f"  saklanan        : {stats.stored}")
    print(f"  tam tekrar      : {stats.exact_duplicates}")
    print(f"  yakin tekrar    : {stats.near_duplicates}")
    print(f"  kapsam disi     : {stats.filtered_out}")
    print(f"  hata            : {stats.errors}")
    return 0


def cmd_embed(limit: int) -> int:
    from politikdesk.nlp import repository as nlp_repo
    from politikdesk.nlp.embedder import build_backend, embedding_text

    rows = nlp_repo.pending_embedding(limit)
    if not rows:
        print("Bekleyen makale yok.")
        return 0

    backend = build_backend()
    vectors = backend.embed([embedding_text(r["title"], r["excerpt"]) for r in rows])
    saved = nlp_repo.save_embeddings(
        {row["id"]: v for row, v in zip(rows, vectors, strict=True)}
    )
    print(f"{saved} makale embed edildi (backend={backend.name}).")
    if not backend.is_production_ready:
        print("  UYARI: uretim icin uygun olmayan yerel embedder kullanildi.")
        print("  D16 karari icin: docs/embedding-benchmark.md")
    return 0


def cmd_entities(limit: int) -> int:
    from politikdesk.nlp import entities as ner
    from politikdesk.nlp import repository as nlp_repo

    rows = nlp_repo.pending_entities(limit)
    if not rows:
        print("Bekleyen makale yok.")
        return 0

    processed = []
    for row in rows:
        found = ner.extract(row["title"], row["excerpt"])
        ids = [
            nlp_repo.upsert_entity(
                e,
                aliases=ner.INSTITUTIONS.get(e.canonical_name, ())
                if e.entity_type == "institution" else (),
            )
            for e in found
        ]
        nlp_repo.link_article_entities(row["id"], ids)
        processed.append(row["id"])

    nlp_repo.mark_entities_extracted(processed)
    print(f"{len(processed)} makalede varlik cikarimi yapildi.")
    return 0


def cmd_health() -> int:
    from politikdesk.ingestion.repository import health_report

    report = health_report()
    print(f"{'kaynak':<16}{'tier':<6}{'durum':<10}{'24s':<6}{'toplam':<8}{'son basari'}")
    print("-" * 70)
    for row in report:
        hours = row["hours_since_success"]
        print(
            f"{row['slug']:<16}T{row['tier']:<5}{row['status']:<10}"
            f"{row['articles_24h']:<6}{row['articles_total']:<8}"
            f"{f'{hours} sa' if hours is not None else '-'}"
        )
        if row["last_error"]:
            print(f"    hata: {row['last_error'][:100]}")
    return 0 if all(r["status"] != "red" for r in report) else 1


def cmd_purge() -> int:
    from politikdesk.ingestion.repository import purge_expired_bodies

    count = purge_expired_bodies()
    print(f"{count} kayitta lead_paragraph silindi (30 gun TTL).")
    return 0


def cmd_cluster(limit: int) -> int:
    """Bekleyen makaleleri olaylara atar (F2-01)."""
    from politikdesk.clustering.pipeline import run

    stats = run(limit)
    print("Kumeleme turu tamamlandi:")
    for key, value in stats.as_dict().items():
        print(f"  {key:18s}: {value}")
    return 0


def main() -> int:
    configure_logging()

    parser = argparse.ArgumentParser(description="PolitikDesk ingestion araci")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sync", help="sources.yml -> veritabani")

    run = sub.add_parser("run", help="Toplama turu")
    run.add_argument("--source", help="Yalnizca bu kaynak")
    run.add_argument("--no-scope-filter", action="store_true",
                     help="Konu kapsam filtresini kapat (teshis icin)")

    embed = sub.add_parser("embed", help="Bekleyen makaleleri embed et")
    embed.add_argument("--limit", type=int, default=200)

    ents = sub.add_parser("entities", help="Varlik cikarimi")
    ents.add_argument("--limit", type=int, default=500)

    cluster = sub.add_parser("cluster", help="Bekleyen makaleleri olaylara ata")
    cluster.add_argument("--limit", type=int, default=200)

    sub.add_parser("health", help="Kaynak saglik raporu")
    sub.add_parser("purge", help="Suresi gecmis govdeleri sil")

    args = parser.parse_args()

    if args.command == "sync":
        return cmd_sync()
    if args.command == "run":
        return cmd_run(args.source, args.no_scope_filter)
    if args.command == "embed":
        return cmd_embed(args.limit)
    if args.command == "entities":
        return cmd_entities(args.limit)
    if args.command == "cluster":
        return cmd_cluster(args.limit)
    if args.command == "health":
        return cmd_health()
    if args.command == "purge":
        return cmd_purge()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
