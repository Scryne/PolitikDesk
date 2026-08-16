"""Ingestion boru hattını elle çalıştırma aracı.

Celery beat 5 dakikada bir aynı işi yapar (F1-05); bu araç geliştirme,
teşhis ve ilk doldurma (backfill) içindir.

Kullanım:
    python -m scripts.ingest sync            # sources.yml -> veritabanı
    python -m scripts.ingest run             # tüm kaynaklardan bir tur
    python -m scripts.ingest run --source aa-ekonomi
    python -m scripts.ingest embed           # bekleyen makaleleri embed et
    python -m scripts.ingest entities        # varlık çıkar
    python -m scripts.ingest reembed --yes   # embedder değişti: sıfırla (B-53)
    python -m scripts.ingest health          # kaynak sağlık raporu
    python -m scripts.ingest purge           # süresi geçmiş gövdeleri sil
"""

from __future__ import annotations

import argparse
import sys

from politikdesk.config import load_env_file
from politikdesk.observability import configure_logging


def cmd_sync() -> int:
    from politikdesk.ingestion.sources import load_all_configs, sync_to_database

    configs = load_all_configs()
    result = sync_to_database(configs)
    print(f"Toplam {len(configs)} kaynak senkronize edildi.")
    print(f"  eklenen: {result['inserted']}  guncellenen: {result['updated']}")
    for cfg in configs:
        mark = "OK" if cfg.verified else "??"
        slug_v = f"{cfg.slug:<28} [{cfg.vertical:<11}]"
        print(f"  [{mark}] {slug_v} T{cfg.tier} {cfg.tos_status:<8} {cfg.adapter}")
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
    saved = nlp_repo.save_embeddings({row["id"]: v for row, v in zip(rows, vectors, strict=True)})
    print(f"{saved} makale embed edildi (backend={backend.name}).")
    if not backend.is_production_ready:
        print("  UYARI: uretim icin uygun olmayan yerel embedder kullanildi.")
        print("  D16 karari icin: docs/embedding-benchmark.md")
    return 0


def cmd_reembed(yes: bool) -> int:
    """Embedder degistiginde turetilmis katmani sifirlar (B-53).

    Makalelerin HAM verisi korunur; embedding, olaylar ve olay iliskileri
    dusurulur. Ardindan `embed` + `cluster` yeniden kosulmalidir.
    """
    from politikdesk.nlp import repository as nlp_repo
    from politikdesk.nlp.embedder import build_backend

    backend = build_backend()
    if not backend.is_production_ready:
        print(f"Iptal: aktif embedder '{backend.name}' uretim icin uygun degil.")
        print("  Sifirlamadan once PD_EMBEDDING_PROVIDER ayarlanmali (D16).")
        return 2

    if not yes:
        print("Bu islem TUM olaylari ve embedding'leri siler; makaleler kalir.")
        print(f"Yeni embedder: {backend.name}")
        print("Onaylamak icin --yes ile tekrar calistirin.")
        return 1

    counts = nlp_repo.reset_derived_state()
    print("Turetilmis katman sifirlandi:")
    for key, value in counts.items():
        print(f"  {key:18s}: {value}")
    print("\nSirada: `make embed` ve `make cluster`.")
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
                if e.entity_type == "institution"
                else (),
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


def cmd_claims(limit: int) -> int:
    """Olaylardan iddia cikarir (F2-06). ANTHROPIC_API_KEY gerekir."""
    from politikdesk.llm.errors import LLMNotConfigured
    from politikdesk.nlp.claims_pipeline import run

    try:
        stats = run(limit)
    except LLMNotConfigured as exc:
        print(f"Iddia cikarimi yapilamadi: {exc}")
        print("  Faz 2 G2 kosul 5 ve F2-07 DoD bu adima bagli (B-58).")
        return 2
    print("Iddia cikarimi tamamlandi:")
    for key, value in stats.as_dict().items():
        print(f"  {key:18s}: {value}")
    return 0


def cmd_reclaim(yes: bool) -> int:
    """Eski prompt surumuyle cikarilmis iddialari yeniden cikarir (B-70).

    Yikici islem: iddialar ve kanit baglari SILINIR, sonra claims.v2 ile
    yeniden uretilir. Onay olmadan calismaz.
    """
    from politikdesk.llm.errors import LLMNotConfigured
    from politikdesk.nlp.claims import PROMPT_VERSION
    from politikdesk.nlp.claims_pipeline import reextract, stale_events

    stale = stale_events()
    if not stale:
        print(f"Tum iddialar guncel prompt surumunde ({PROMPT_VERSION}).")
        return 0

    total = sum(int(r["claim_count"]) for r in stale)
    print(f"Eski surumle cikarilmis {total} iddia, {len(stale)} olayda:")
    for row in stale:
        versions = ", ".join(v for v in row["versions"] if v)
        print(f"  olay {row['event_id']}: {row['claim_count']} iddia  [{versions}]")

    if not yes:
        print(f"\nBu iddialar SILINIP {PROMPT_VERSION} ile yeniden cikarilacak.")
        print("Onaylamak icin: python -m scripts.ingest reclaim --yes")
        return 1

    try:
        stats = reextract([int(r["event_id"]) for r in stale])
    except LLMNotConfigured as exc:
        print(f"Yeniden cikarim yapilamadi: {exc}")
        return 2

    print("\nYeniden cikarim tamamlandi:")
    for key, value in stats.as_dict().items():
        print(f"  {key:18s}: {value}")
    print("\nSonraki adim: python -m scripts.ingest evidence")
    return 0


def cmd_briefing(slot: str, send: bool) -> int:
    """Sabah/aksam brifingi uretir (F3-16) ve istege bagli gonderir (F3-17)."""
    from politikdesk.briefing import generator

    result = generator.generate(slot)  # type: ignore[arg-type]
    print(f"Brifing uretildi: #{result['briefing_id']} ({slot}, {result['briefing_date']})")
    print(f"  olay             : {len(result['events'])}")
    print(f"  beklenen gelisme : {len(result['upcoming'])}")
    print(f"  dogrulanmamis    : {len(result['unverified'])}")

    if send:
        from politikdesk.briefing.mailer import send_briefing

        outcome = send_briefing(result["briefing_id"])
        if outcome.sent:
            print("  gonderim         : basarili")
        elif outcome.skipped_reason == "smtp_unconfigured":
            print("  gonderim         : atlandi (PD_SMTP_HOST bos) — brifing yine uretildi")
        else:
            print(f"  gonderim         : basarisiz — {outcome.error or outcome.skipped_reason}")
    return 0


def cmd_metrics(day: str | None, backfill: int) -> int:
    """Urun metriklerinin gunluk toplamasi (F3-19)."""
    from datetime import date, timedelta

    from politikdesk import metrics

    target = date.fromisoformat(day) if day else date.today()
    for offset in range(max(backfill, 1)):
        result = metrics.daily_rollup(target - timedelta(days=offset))
        if offset == 0:
            for m in result["metrics"]:
                value = "—" if m["value"] is None else f"{m['value']:.2f}"
                print(
                    f"  {m['status']:8s} {m['label']:26s} {value:>9s} {m['unit']:5s}"
                    f" (hedef {m['target']}, n={m['sample_size']})"
                )
    print(f"\n{max(backfill, 1)} gun toplandi.")
    return 0


def cmd_evidence(limit: int) -> int:
    """Kanit durumu ve salience hesaplar (F2-12, F2-13, F2-15)."""
    from politikdesk.evidence.pipeline import run

    stats = run(limit)
    print("Kanit motoru turu tamamlandi:")
    for key, value in stats.as_dict().items():
        print(f"  {key:18s}: {value}")
    return 0


def cmd_context(limit: int) -> int:
    """Tarihsel baglam baglari kurar (F2-17)."""
    from politikdesk.context.related import run

    stats = run(limit)
    print("Baglam turu tamamlandi:")
    for key, value in stats.items():
        print(f"  {key:18s}: {value}")
    return 0


def cmd_memory(limit: int) -> int:
    """Siyasi hafiza ve olay iliskilerini degerlendirir (Spec v3.4 §14.1)."""
    from politikdesk.political_memory.orchestrator import process_pending_political_relations

    stats = process_pending_political_relations(limit)
    print("Siyasi hafiza iliski turu tamamlandi:")
    for key, value in stats.items():
        print(f"  {key:20s}: {value}")
    return 0


def main() -> int:
    # Sağlayıcı anahtarları (`ANTHROPIC_API_KEY`, `NVIDIA_API_KEY`…) `PD_`
    # önekli olmadığı için `Settings` onları okumaz; yerel koşumda ortama
    # ancak buradan girer. Docker'da compose'un `env_file`'ı zaten yapıyor.
    load_env_file()
    configure_logging()

    parser = argparse.ArgumentParser(description="PolitikDesk ingestion araci")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sync", help="sources.yml -> veritabani")

    run = sub.add_parser("run", help="Toplama turu")
    run.add_argument("--source", help="Yalnizca bu kaynak")
    run.add_argument(
        "--no-scope-filter", action="store_true", help="Konu kapsam filtresini kapat (teshis icin)"
    )

    embed = sub.add_parser("embed", help="Bekleyen makaleleri embed et")
    embed.add_argument("--limit", type=int, default=200)

    reembed = sub.add_parser(
        "reembed", help="Embedder degistiginde turetilmis katmani sifirla (B-53)"
    )
    reembed.add_argument("--yes", action="store_true", help="Onay istemeden calis")

    ents = sub.add_parser("entities", help="Varlik cikarimi")
    ents.add_argument("--limit", type=int, default=500)

    cluster = sub.add_parser("cluster", help="Bekleyen makaleleri olaylara ata")
    cluster.add_argument("--limit", type=int, default=200)

    claims = sub.add_parser("claims", help="Olaylardan iddia cikar (LLM)")
    claims.add_argument("--limit", type=int, default=5)

    reclaim = sub.add_parser(
        "reclaim", help="Eski prompt surumundeki iddialari yeniden cikar (B-70)"
    )
    reclaim.add_argument("--yes", action="store_true", help="Onay istemeden calis")

    briefing = sub.add_parser("briefing", help="Sabah/aksam brifingi uret (F3-16)")
    briefing.add_argument("--slot", choices=["morning", "evening"], default="morning")
    briefing.add_argument("--send", action="store_true", help="E-posta ile gonder")

    metrics_cmd = sub.add_parser("metrics", help="Urun metriklerini topla (F3-19)")
    metrics_cmd.add_argument("--day", help="YYYY-AA-GG (varsayilan: bugun)")
    metrics_cmd.add_argument("--backfill", type=int, default=1, help="Kac gun geriye")

    evidence = sub.add_parser("evidence", help="Kanit durumu + salience")
    evidence.add_argument("--limit", type=int, default=200)

    context = sub.add_parser("context", help="Tarihsel baglam baglari")
    context.add_argument("--limit", type=int, default=50)

    memory = sub.add_parser("memory", help="Siyasi hafiza ve olay iliskileri (S3)")
    memory.add_argument("--limit", type=int, default=50)

    sub.add_parser("health", help="Kaynak saglik raporu")
    sub.add_parser("purge", help="Suresi gecmis govdeleri sil")

    args = parser.parse_args()

    if args.command == "sync":
        return cmd_sync()
    if args.command == "run":
        return cmd_run(args.source, args.no_scope_filter)
    if args.command == "embed":
        return cmd_embed(args.limit)
    if args.command == "reembed":
        return cmd_reembed(args.yes)
    if args.command == "entities":
        return cmd_entities(args.limit)
    if args.command == "cluster":
        return cmd_cluster(args.limit)
    if args.command == "claims":
        return cmd_claims(args.limit)
    if args.command == "reclaim":
        return cmd_reclaim(args.yes)
    if args.command == "briefing":
        return cmd_briefing(args.slot, args.send)
    if args.command == "metrics":
        return cmd_metrics(args.day, args.backfill)
    if args.command == "evidence":
        return cmd_evidence(args.limit)
    if args.command == "context":
        return cmd_context(args.limit)
    if args.command == "memory":
        return cmd_memory(args.limit)
    if args.command == "health":
        return cmd_health()
    if args.command == "purge":
        return cmd_purge()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
