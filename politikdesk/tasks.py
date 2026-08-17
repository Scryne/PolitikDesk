"""Celery görevleri ve zamanlayıcı (F1-05, F1-12, F1-13, F1-15).

F1-05 DoD: 5 dakikalık toplama döngüsü; kaynak başına son çekim zamanı
`sources` tablosunda.
F1-12 DoD: `raw_purge_at` geçmiş kayıtlarda `lead_paragraph` NULL oluyor;
`audit_log`'a yazılıyor.
"""

from __future__ import annotations

from typing import Literal

from celery.schedules import crontab

from politikdesk.config import get_settings
from politikdesk.observability import get_logger
from politikdesk.worker import app

log = get_logger(__name__)

INGESTION_INTERVAL_SECONDS = 300  # 5 dakika (Spec §11.3 adım 1)

# Brifing saatleri yapılandırılabilir; beat zamanlaması modül yüklenirken
# kurulduğu için değerler burada bir kez okunur.
_settings = get_settings()
BRIEFING_MORNING_HOUR = _settings.briefing_morning_hour
BRIEFING_EVENING_HOUR = _settings.briefing_evening_hour
EMBED_BATCH_SIZE = 50
ENTITY_BATCH_SIZE = 100
CLUSTER_BATCH_SIZE = 50
CLAIM_BATCH_EVENTS = 5
EVIDENCE_BATCH_SIZE = 200


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
    Kuyrukta bekleyen varsa bir sonraki partiyi anında tetikler.
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

    if saved >= limit and getattr(self.request, "id", None):
        self.apply_async(args=[limit], countdown=1)

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
                    if e.entity_type == "institution"
                    else (),
                )
                for e in found
            ]
            nlp_repo.link_article_entities(row["id"], entity_ids)
            processed.append(row["id"])
        except Exception:  # noqa: BLE001 — bir makale diğerlerini düşürmez
            log.warning("entity_extraction_failed", article_id=row["id"], exc_info=True)

    nlp_repo.mark_entities_extracted(processed)
    log.info("entity_batch_done", count=len(processed))

    if len(rows) >= limit and getattr(self.request, "id", None):
        self.apply_async(args=[limit], countdown=1)

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
        res = run(limit).as_dict()
        if res.get("processed", 0) >= limit and getattr(self.request, "id", None):
            self.apply_async(args=[limit], countdown=1)
        return res
    except Exception as exc:  # noqa: BLE001
        log.error("cluster_pending_failed", error=type(exc).__name__, detail=str(exc)[:300])
        raise self.retry(exc=exc, countdown=120) from exc


@app.task(name="politikdesk.extract_claims_pending", bind=True, max_retries=2)
def extract_claims_pending(self, limit: int = CLAIM_BATCH_EVENTS) -> dict[str, int]:  # noqa: ANN001
    """Olaylardan iddia çıkarır (F2-06…F2-10).

    LLM kullanır ve bütçe tavanına tabidir. `BudgetExceeded` durumunda
    RETRY EDİLMEZ — tavan zaten aşılmışken tekrar denemek maliyeti
    artırmaktan başka bir işe yaramaz.
    """
    from politikdesk.llm.errors import BudgetExceeded
    from politikdesk.nlp.claims_pipeline import run

    try:
        res = run(limit).as_dict()
        if (
            res.get("events_processed", 0) >= limit
            and not res.get("budget_exceeded")
            and getattr(self.request, "id", None)
        ):
            self.apply_async(args=[limit], countdown=2)
        return res
    except BudgetExceeded as exc:
        log.error("claim_extraction_budget_exceeded", detail=str(exc)[:200])
        return {"errors": 1, "budget_exceeded": 1}
    except Exception as exc:  # noqa: BLE001
        log.error("extract_claims_failed", error=type(exc).__name__, detail=str(exc)[:300])
        raise self.retry(exc=exc, countdown=300) from exc


@app.task(name="politikdesk.score_evidence", bind=True, max_retries=2)
def score_evidence(self, limit: int = EVIDENCE_BATCH_SIZE) -> dict[str, int]:  # noqa: ANN001
    """Kanıt durumu ve salience (F2-12, F2-13, F2-15). LLM ÇAĞRISI YOK."""
    from politikdesk.evidence.pipeline import run

    try:
        res = run(limit).as_dict()
        if res.get("claims_scored", 0) >= limit and getattr(self.request, "id", None):
            self.apply_async(args=[limit], countdown=1)
        return res
    except Exception as exc:  # noqa: BLE001
        log.error("score_evidence_failed", error=type(exc).__name__, detail=str(exc)[:300])
        raise self.retry(exc=exc, countdown=120) from exc


@app.task(name="politikdesk.link_historical_context", bind=True, max_retries=1)
def link_historical_context(self, limit: int = 50) -> dict[str, int]:  # noqa: ANN001
    """Tarihsel bağlam bağları (F2-17)."""
    from politikdesk.context.related import run

    try:
        res = run(limit)
        if res.get("events_processed", 0) >= limit and getattr(self.request, "id", None):
            self.apply_async(args=[limit], countdown=1)
        return res
    except Exception as exc:  # noqa: BLE001
        log.error("link_historical_context_failed", error=type(exc).__name__, detail=str(exc)[:300])
        raise self.retry(exc=exc, countdown=120) from exc


@app.task(
    name="politikdesk.link_political_relations",
    bind=True,
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def link_political_relations(self, limit: int = 50) -> dict[str, int]:  # noqa: ANN001
    """Siyasi olaylar için deterministik ilişki çıkarma ve hesap verebilirlik eşleme görevi (S3)."""
    from politikdesk.political_memory.orchestrator import process_pending_political_relations

    try:
        res = process_pending_political_relations(limit)
        if res.get("events_processed", 0) >= limit and getattr(self.request, "id", None):
            self.apply_async(args=[limit], countdown=1)
        return res
    except Exception as exc:  # noqa: BLE001
        log.error("political_relations_failed", error=type(exc).__name__, detail=str(exc)[:300])
        raise self.retry(exc=exc, countdown=180) from exc


@app.task(name="politikdesk.match_scheduled_events", bind=True, max_retries=1)
def match_scheduled_events(self) -> dict[str, int]:  # noqa: ANN001
    """Beklenen gelişme -> gerçekleşen olay eşleştirmesi (F2-19)."""
    from politikdesk.context.scheduler_match import match_pending

    try:
        return match_pending()
    except Exception as exc:  # noqa: BLE001
        log.error("match_scheduled_events_failed", error=type(exc).__name__, detail=str(exc)[:300])
        raise self.retry(exc=exc, countdown=120) from exc


@app.task(name="politikdesk.purge_expired_bodies")
def purge_expired_bodies() -> int:
    """30 günü geçmiş `lead_paragraph` alanlarını siler (F1-12)."""
    from politikdesk.ingestion.repository import purge_expired_bodies as purge

    return purge()


@app.task(name="politikdesk.generate_briefing", bind=True, max_retries=1)
def generate_briefing(self, slot: Literal["morning", "evening"] = "morning") -> dict[str, object]:  # noqa: ANN001
    """Sabah/akşam brifingi üretir ve gönderir (F3-16, F3-17).

    Üretim ve gönderim ayrı ele alınır: SMTP yokken de brifing üretilir
    ve `/briefing/{tarih}` sayfasında görünür. Gönderim hatası turu
    başarısız saymaz — brifing zaten kayıtlıdır.
    """
    from politikdesk.briefing.generator import generate
    from politikdesk.briefing.mailer import send_briefing

    try:
        result = generate(slot)
    except Exception as exc:  # noqa: BLE001
        log.error("briefing_failed", slot=slot, error=type(exc).__name__, detail=str(exc)[:300])
        raise self.retry(exc=exc, countdown=300) from exc

    outcome = send_briefing(int(result["briefing_id"]))
    return {
        "briefing_id": result["briefing_id"],
        "slot": slot,
        "events": len(result["events"]),
        "unverified": len(result["unverified"]),
        **outcome.as_dict(),
    }


@app.task(name="politikdesk.rollup_metrics")
def rollup_metrics(window_days: int = 7) -> dict[str, object]:
    """Sekiz ürün metriğinin günlük toplaması (F3-19).

    Gün bitmeden koşar (23:50): o günün aktif dakikaları tamamlanmış
    olur, oran metrikleri zaten kayan pencerededir.
    """
    from politikdesk import metrics

    result = metrics.daily_rollup(window_days=window_days)
    return {"day": result["day"], "written": result["written"]}


@app.task(name="politikdesk.check_source_health")
def check_source_health() -> list[str]:
    """6 saattir veri vermeyen kaynakları uyarır (F1-19)."""
    from politikdesk.ingestion.repository import health_report

    unhealthy = [r["slug"] for r in health_report() if r["status"] == "red"]
    if unhealthy:
        log.error(
            "sources_unhealthy",
            sources=unhealthy,
            hint="6 saattir veri yok veya hiç başarılı çekim olmadı",
        )
    return unhealthy


@app.task(name="politikdesk.check_pipeline_health")
def check_pipeline_health() -> list[dict[str, object]]:
    """Bir aşamada birikme var mı? (F4-05, B-78)

    `check_source_health` boru hattının GİRİŞİNE bakar; bu görev
    içerisine bakar. 13 Ağustos'ta toplama çalışırken kümeleme durmuştu
    ve 13 saat boyunca hiçbir gösterge bunu söylemedi.
    """
    from politikdesk import pipeline_health

    return pipeline_health.check_and_log()


@app.task(name="politikdesk.check_llm_budget")
def check_llm_budget() -> dict[str, object]:
    """Bütçe eşiğini kontrol eder, gerekirse uyarı gönderir (F4-07).

    Bütçe zaten her çağrı öncesi denetleniyor; bu görev *çağrı olmasa
    bile* eşiğin görülmesini sağlar — ay sonuna doğru tavana yaklaşıp
    üretimin duracağını önceden bilmek gerekir.
    """
    from politikdesk.llm.budget import BudgetGuard

    return BudgetGuard().alert_if_needed()


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
    # İddia çıkarımı kümelemeden sonra gelir; LLM maliyeti nedeniyle
    # seyrek koşar (Spec §11.5 bütçe disiplini).
    "claims-every-10-minutes": {
        "task": "politikdesk.extract_claims_pending",
        "schedule": 600.0,
    },
    # Kanıt motoru ucuzdur (LLM yok) — sık koşar ki durumlar tazelensin.
    "evidence-every-5-minutes": {
        "task": "politikdesk.score_evidence",
        "schedule": 300.0,
    },
    "context-every-30-minutes": {
        "task": "politikdesk.link_historical_context",
        "schedule": 1800.0,
    },
    "political-relations-every-15-minutes": {
        "task": "politikdesk.link_political_relations",
        "schedule": 900.0,
    },
    # Takvim eşleştirmesi: veri yayım saatleri bellidir, saatlik yeter.
    "scheduler-match-hourly": {
        "task": "politikdesk.match_scheduled_events",
        "schedule": crontab(minute=20),
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
    # Aşama sağlığı (B-78). Kaynak kontrolünden 30 dakika kaydırıldı ki
    # iki alarm aynı loga aynı anda düşüp birbirini gizlemesin.
    "pipeline-health-hourly": {
        "task": "politikdesk.check_pipeline_health",
        "schedule": crontab(minute=35),
    },
    # Bütçe eşiği (F4-07). Günde iki kez: sabah brifinginden önce ve
    # gün ortasında — tavana çarpmadan önce haber alınsın.
    "llm-budget-check": {
        "task": "politikdesk.check_llm_budget",
        "schedule": crontab(hour="7,15", minute=45),
    },
    # --- Faz 3 ---
    # Brifing saatleri Spec §14.1 kalem 12'den: sabah 08:00, akşam 20:00.
    # `crontab` konteynerin saat diliminde çalışır; compose'da TZ
    # Europe/Istanbul verilir ki 08:00 gerçekten sabah olsun.
    "briefing-morning": {
        "task": "politikdesk.generate_briefing",
        "schedule": crontab(hour=BRIEFING_MORNING_HOUR, minute=0),
        "kwargs": {"slot": "morning"},
    },
    "briefing-evening": {
        "task": "politikdesk.generate_briefing",
        "schedule": crontab(hour=BRIEFING_EVENING_HOUR, minute=0),
        "kwargs": {"slot": "evening"},
    },
    # Metrik toplama gün BİTMEDEN koşar: o günün aktif dakikaları
    # tamamlanmış olsun (F3-19).
    "metrics-rollup-nightly": {
        "task": "politikdesk.rollup_metrics",
        "schedule": crontab(hour=23, minute=50),
    },
}
