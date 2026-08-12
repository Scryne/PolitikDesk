"""Celery görevleri ve zamanlayıcı (F1-05, F1-12, F1-13, F1-15).

F1-05 DoD: 5 dakikalık toplama döngüsü; kaynak başına son çekim zamanı
`sources` tablosunda.
F1-12 DoD: `raw_purge_at` geçmiş kayıtlarda `lead_paragraph` NULL oluyor;
`audit_log`'a yazılıyor.
"""

from __future__ import annotations

from celery.schedules import crontab

from politikdesk.observability import get_logger
from politikdesk.worker import app

log = get_logger(__name__)

INGESTION_INTERVAL_SECONDS = 300  # 5 dakika (Spec §11.3 adım 1)
EMBED_BATCH_SIZE = 50
ENTITY_BATCH_SIZE = 100
CLUSTER_BATCH_SIZE = 50


@app.task(name="politikdesk.ingest_all", bind=True, max_retries=2)
def ingest_all(self) -> dict[str, int]:  # noqa: ANN001
    """Tüm aktif kaynaklardan toplama turu."""
    from politikdesk.ingestion.pipeline import Pipeline

    try:
        stats = Pipeline().run_all()
    except Exception as exc:  # noqa: BLE001
        log.error("ingest_all_failed", error=type(exc).__name__, detail=str(exc)[:300])
        raise self.retry(exc=exc, countdown=60) from exc

    return {
        "fetched": stats.fetched,
        "stored": stats.stored,
        "exact_duplicates": stats.exact_duplicates,
        "near_duplicates": stats.near_duplicates,
        "filtered_out": stats.filtered_out,
        "errors": stats.errors,
    }


@app.task(name="politikdesk.embed_pending", bind=True, max_retries=3)
def embed_pending(self, limit: int = EMBED_BATCH_SIZE) -> int:  # noqa: ANN001
    """Bekleyen makaleleri embed eder (F1-13).

    DoD: hata durumunda kuyruğa geri alınıyor — `self.retry` bunu sağlar.
    """
    from politikdesk.nlp import repository as nlp_repo
    from politikdesk.nlp.embedder import build_backend, embedding_text

    rows = nlp_repo.pending_embedding(limit)
    if not rows:
        return 0

    try:
        backend = build_backend()
        texts = [embedding_text(r["title"], r["excerpt"]) for r in rows]
        vectors = backend.embed(texts)
    except Exception as exc:  # noqa: BLE001
        log.warning("embedding_failed", count=len(rows), error=type(exc).__name__)
        raise self.retry(exc=exc, countdown=120) from exc

    saved = nlp_repo.save_embeddings(
        {row["id"]: vector for row, vector in zip(rows, vectors, strict=True)}
    )
    log.info("embedding_batch_done", count=saved, backend=backend.name)
    return saved


@app.task(name="politikdesk.extract_entities_pending", bind=True, max_retries=2)
def extract_entities_pending(self, limit: int = ENTITY_BATCH_SIZE) -> int:  # noqa: ANN001
    """Bekleyen makalelerden varlık çıkarır (F1-15, F1-16)."""
    from politikdesk.nlp import entities as ner
    from politikdesk.nlp import repository as nlp_repo

    rows = nlp_repo.pending_entities(limit)
    if not rows:
        return 0

    processed: list[int] = []
    for row in rows:
        try:
            found = ner.extract(row["title"], row["excerpt"])
            entity_ids = [
                nlp_repo.upsert_entity(
                    e,
                    aliases=ner.INSTITUTIONS.get(e.canonical_name, ())
                    if e.entity_type == "institution" else (),
                )
                for e in found
            ]
            nlp_repo.link_article_entities(row["id"], entity_ids)
            processed.append(row["id"])
        except Exception:  # noqa: BLE001 — bir makale diğerlerini düşürmez
            log.warning("entity_extraction_failed", article_id=row["id"], exc_info=True)

    nlp_repo.mark_entities_extracted(processed)
    log.info("entity_batch_done", count=len(processed))
    return len(processed)


@app.task(name="politikdesk.cluster_pending", bind=True, max_retries=2)
def cluster_pending(self, limit: int = CLUSTER_BATCH_SIZE) -> dict[str, int]:  # noqa: ANN001
    """Bekleyen makaleleri olaylara atar (F2-01).

    Embedding ve varlık çıkarımından SONRA çalışır (Spec §11.3 adım 5);
    ikisi de tamamlanmamış makaleler `pending_clustering` tarafından zaten
    dışlanır — varlık kısıtı olmadan kümeleme yanlış birleştirme üretir.
    """
    from politikdesk.clustering.pipeline import run

    try:
        return run(limit).as_dict()
    except Exception as exc:  # noqa: BLE001
        log.error("cluster_pending_failed", error=type(exc).__name__, detail=str(exc)[:300])
        raise self.retry(exc=exc, countdown=120) from exc


@app.task(name="politikdesk.purge_expired_bodies")
def purge_expired_bodies() -> int:
    """30 günü geçmiş `lead_paragraph` alanlarını siler (F1-12)."""
    from politikdesk.ingestion.repository import purge_expired_bodies as purge

    return purge()


@app.task(name="politikdesk.check_source_health")
def check_source_health() -> list[str]:
    """6 saattir veri vermeyen kaynakları uyarır (F1-19)."""
    from politikdesk.ingestion.repository import health_report

    unhealthy = [r["slug"] for r in health_report() if r["status"] == "red"]
    if unhealthy:
        log.error("sources_unhealthy", sources=unhealthy,
                  hint="6 saattir veri yok veya hiç başarılı çekim olmadı")
    return unhealthy


app.conf.beat_schedule = {
    # Spec §11.3: her 5 dakikada bir toplama
    "ingest-every-5-minutes": {
        "task": "politikdesk.ingest_all",
        "schedule": INGESTION_INTERVAL_SECONDS,
    },
    # Toplamadan hemen sonra embed: "60 sn içinde embed" DoD'u için sık koşar
    "embed-every-minute": {
        "task": "politikdesk.embed_pending",
        "schedule": 60.0,
    },
    "entities-every-2-minutes": {
        "task": "politikdesk.extract_entities_pending",
        "schedule": 120.0,
    },
    # Kümeleme, varlık çıkarımından sonra gelir (Spec §11.3 adım 5).
    # Varlık turu 2 dakikada bir koşuyor; kümeleme 3 dakikada bir koşarak
    # her makalenin varlıklarının hazır olmasına şans tanır.
    "cluster-every-3-minutes": {
        "task": "politikdesk.cluster_pending",
        "schedule": 180.0,
    },
    # Saklama politikası: günlük purge (Spec §9.3)
    "purge-daily": {
        "task": "politikdesk.purge_expired_bodies",
        "schedule": crontab(hour=3, minute=15),
    },
    "health-check-hourly": {
        "task": "politikdesk.check_source_health",
        "schedule": crontab(minute=5),
    },
}
