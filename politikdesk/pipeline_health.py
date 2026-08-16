"""Boru hattı *aşama* sağlığı — sessiz kopma alarmı (F4-05, B-78).

Kaynak sağlığı (F1-19) "veri geliyor mu?" sorusunu yanıtlar. Bu modül
farklı bir soru sorar: **gelen veri boru hattının sonuna kadar gidiyor
mu?**

Neden ayrı bir izleyici gerekti (13 Ağustos 2026, B-77):

    Toplama çalışıyordu, kaynak panosu yemyeşildi, 467 test geçiyordu.
    Ama `pd-beat` eski bir imajla koşuyordu ve kümeleme görevi hiç
    zamanlanmamıştı. 29 makalenin 18'i gömülüp varlıkları çıkarıldıktan
    sonra `event_id IS NULL` halinde askıda kaldı — **13 saat boyunca
    hiçbir gösterge kırmızıya dönmedi.**

Aradaki fark şu: kaynak sağlığı boru hattının *girişine* bakar, dağıtım
denetleyicisi (`scripts/check_deployment.py`) *kodun kendisine* bakar.
İkisinin arasında bir kör nokta vardı: boru hattı ayakta ve güncel
koddayken bile bir aşamada birikme olabilir (worker düşer, kuyruk tıkanır,
LLM bütçesi biter). Bu modül o kör noktayı kapatır.

Tasarım kuralı: **eşikler işin ritmine bağlıdır, takvime değil.** Embed
görevi 60 saniyede bir koşuyorsa, 2 saatlik bir birikme arıza demektir.
İddia çıkarımı 10 dakikada bir 5 olay işliyorsa aynı süre normaldir.
Bu yüzden her aşamanın kendi eşiği vardır ve eşik, görevin zamanlama
sıklığından türetilmiştir.

⛔ Bu modül `politikdesk.llm` import ETMEZ ve kanıt motoruna dokunmaz;
yalnızca sayar.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from politikdesk.db import connection
from politikdesk.evidence.rules import engine_version
from politikdesk.nlp.claims_pipeline import MAX_CLAIM_ATTEMPTS
from politikdesk.observability import get_logger
from politikdesk.political_memory.orchestrator import RELATION_ENGINE_VERSION

log = get_logger(__name__)

StageStatus = Literal["green", "amber", "red"]

# Bir aşamada bekleyen en eski öğe bu saati aşarsa alarm. Değerler
# `tasks.py`'deki beat sıklıklarından türetildi: normal işleyişte hiçbir
# öğe burada listelenen sürenin yakınına bile gelmez.
#
#   aşama               beat sıklığı   eşik    kat
#   embed               60 sn          2 sa    120x
#   entities            2 dk           2 sa     60x
#   cluster             3 dk           3 sa     60x
#   claims              10 dk          6 sa     36x   (LLM + bütçe tavanı)
#   evidence            5 dk           3 sa     36x
#   context             30 dk          6 sa     12x
#   political_relations 15 dk          6 sa     24x
#   scheduler_match     1 sa           24 sa    24x
#
# Kat payı bilerek yüksek: bu alarm "yavaş" demek için değil, "kopmuş"
# demek için var. Yanlış alarm veren bir alarm kapatılır.
AMBER_RATIO = 0.5  # eşiğin yarısına gelen aşama sarı


@dataclass(frozen=True)
class Stage:
    """Boru hattının bir adımı ve birikmesini ölçen sorgu."""

    key: str
    label: str
    threshold_hours: float
    sql: str
    hint: str
    params: tuple[Any, ...] | Callable[[], tuple[Any, ...]] = ()

    def get_params(self) -> tuple[Any, ...]:
        if callable(self.params):
            return self.params()
        return self.params


# Her sorgu iki sütun döndürür:
#   backlog      — bekleyen öğe sayısı
#   oldest_hours — en eski bekleyen öğenin kaç saattir beklediği (NULL = yok)
#
# Yüklemler, o aşamayı fiilen koşan görevin yüklemiyle BİREBİR aynıdır.
# Ayrışırlarsa izleyici, işlenmeyecek bir öğeyi bekliyor sanar ya da
# tersi — gerçek birikmeyi kaçırır.
STAGES: tuple[Stage, ...] = (
    Stage(
        key="embed",
        label="Embedding",
        threshold_hours=2,
        # nlp/repository.py::pending_embedding
        sql="""
            SELECT count(*) AS backlog,
                   EXTRACT(EPOCH FROM (now() - min(first_seen_at))) / 3600
                     AS oldest_hours
            FROM articles WHERE embedded_at IS NULL
        """,
        hint="worker ayakta mı? `make workers` · embed-local ekstrası kurulu mu?",
    ),
    Stage(
        key="entities",
        label="Varlık çıkarımı",
        threshold_hours=2,
        # nlp/repository.py::pending_entities
        sql="""
            SELECT count(*) AS backlog,
                   EXTRACT(EPOCH FROM (now() - min(first_seen_at))) / 3600
                     AS oldest_hours
            FROM articles WHERE entities_extracted_at IS NULL
        """,
        hint="worker ayakta mı? `make entities` ile elle koşulabilir",
    ),
    Stage(
        key="cluster",
        label="Olay kümeleme",
        threshold_hours=3,
        # clustering/repository.py::pending_clustering — üç koşul da aynı
        sql="""
            SELECT count(*) AS backlog,
                   EXTRACT(EPOCH FROM (now() - min(
                       COALESCE(published_at, first_seen_at)))) / 3600
                     AS oldest_hours
            FROM articles
            WHERE event_id IS NULL
              AND embedding IS NOT NULL
              AND entities_extracted_at IS NOT NULL
        """,
        hint="beat'te `cluster-every-3-minutes` zamanlaması var mı? "
        "`make deploy-check` bayat imajı yakalar",
    ),
    Stage(
        key="claims",
        label="İddia çıkarımı",
        threshold_hours=6,
        # nlp/claims_pipeline.py::PENDING_EVENTS_SQL ile AYNI yüklem (F5-16).
        # Deneme hakkı dolmuş olaylar burada sayılmaz: onlar birikme
        # değil, sonuçlanmış bir karardır ("bu metinden iddia çıkmıyor").
        # Sayılsalardı alarm kalıcı olarak kırmızı kalır ve susturulurdu.
        sql="""
            SELECT count(*) AS backlog,
                   EXTRACT(EPOCH FROM (now() - min(e.last_update_at))) / 3600
                     AS oldest_hours
            FROM events e
            WHERE e.merged_into_id IS NULL
              AND e.article_count > 0
              AND (
                    e.claims_attempted_at IS NULL
                 OR e.last_update_at > e.claims_attempted_at
                 OR (
                      NOT EXISTS (SELECT 1 FROM claims c WHERE c.event_id = e.id)
                      AND e.claims_attempt_count < %s
                    )
              )
        """,
        params=(MAX_CLAIM_ATTEMPTS,),
        hint="LLM bütçesi dolmuş olabilir (`/admin/metrics` bütçe kutusu) "
        "ya da sağlayıcı hata veriyor",
    ),
    Stage(
        key="evidence",
        label="Kanıt puanlaması",
        threshold_hours=3,
        # evidence/pipeline.py::score_claims — aynı motor sürümü ve yeni kanıt yüklemi (F5-17)
        sql="""
            SELECT count(*) AS backlog,
                   EXTRACT(EPOCH FROM (now() - min(
                       COALESCE((status_reason->>'computed_at')::timestamptz, created_at)
                   ))) / 3600 AS oldest_hours
            FROM claims c
            WHERE status_reason IS NULL
               OR status_reason->>'engine_version' IS DISTINCT FROM %s
               OR EXISTS (
                    SELECT 1 FROM evidence ev
                    WHERE ev.claim_id = c.id
                      AND ev.created_at > (c.status_reason->>'computed_at')::timestamptz
                  )
        """,
        params=lambda: (engine_version(),),
        hint="kanıt motoru LLM kullanmaz; birikme varsa worker durmuştur",
    ),
    Stage(
        key="context",
        label="Tarihsel bağlam",
        threshold_hours=6,
        # context/related.py::run — aynı ilişkilendirilmemiş olay yüklemi (F2-17)
        sql="""
            SELECT count(*) AS backlog,
                   EXTRACT(EPOCH FROM (now() - min(e.last_update_at))) / 3600
                     AS oldest_hours
            FROM events e
            WHERE e.merged_into_id IS NULL
              AND e.centroid_embedding IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM event_relations r WHERE r.from_event_id = e.id
              )
              AND NOT EXISTS (
                SELECT 1 FROM audit_log a
                WHERE a.target = 'events/' || e.id
                  AND a.action = 'context_evaluated'
                  AND a.created_at >= e.last_update_at
              )
        """,
        hint="beat'te `context-every-30-minutes` zamanlaması var mı? `make workers`",
    ),
    Stage(
        key="political_relations",
        label="Siyasi ilişkiler",
        threshold_hours=6,
        # political_memory/orchestrator.py::process_pending_political_relations (S3)
        sql="""
            SELECT count(*) AS backlog,
                   EXTRACT(EPOCH FROM (now() - min(e.last_update_at))) / 3600
                     AS oldest_hours
            FROM events e
            WHERE e.merged_into_id IS NULL
              AND (
                  e.vertical = 'legislation'
                  OR EXISTS (
                      SELECT 1 FROM claims c
                      WHERE c.event_id = e.id AND c.claim_type = 'promise'
                  )
              )
              AND NOT EXISTS (
                  SELECT 1 FROM event_relations r
                  WHERE r.from_event_id = e.id
                    AND r.engine_version = %s
                    AND r.updated_at >= e.last_update_at
              )
              AND NOT EXISTS (
                  SELECT 1 FROM audit_log a
                  WHERE a.target = 'events/' || e.id
                    AND a.action = 'political_relations_evaluated'
                    AND a.payload->>'engine_version' = %s
                    AND a.created_at >= e.last_update_at
              )
        """,
        params=(RELATION_ENGINE_VERSION, RELATION_ENGINE_VERSION),
        hint="beat'te `political-relations-every-15-minutes` zamanlaması var mı?",
    ),
    Stage(
        key="scheduler_match",
        label="Takvim eşleştirmesi",
        threshold_hours=24,
        # context/scheduler_match.py::match_pending (F2-19)
        sql="""
            SELECT count(*) AS backlog,
                   EXTRACT(EPOCH FROM (now() - min(expected_at))) / 3600
                     AS oldest_hours
            FROM scheduled_events
            WHERE status = 'pending'
              AND linked_event_id IS NULL
              AND expected_at < now()
        """,
        hint=(
            "beat'te `scheduler-match-hourly` zamanlaması var mı? "
            "Eşleşmeyen resmî takvim olayları incelenmeli"
        ),
    ),
)


# Birikme sayısıyla değil, *son çalışma zamanıyla* ölçülen aşamalar.
# Bunlarda "bekleyen öğe" kavramı yok: brifing ya üretildi ya üretilmedi.
@dataclass(frozen=True)
class Heartbeat:
    key: str
    label: str
    threshold_hours: float
    sql: str
    hint: str


HEARTBEATS: tuple[Heartbeat, ...] = (
    Heartbeat(
        key="ingest",
        label="Toplama",
        # 5 dakikada bir koşar; 24 saat hiç yeni makale gelmemesi, tatil
        # günü bile olsa, 7 kaynağın tamamının sustuğu anlamına gelir.
        threshold_hours=24,
        sql="SELECT max(first_seen_at) AS last_at FROM articles",
        hint="`make ingest` elle koşup çıktıya bakın; `/admin/` kaynak panosu",
    ),
    Heartbeat(
        key="briefing",
        label="Brifing",
        # Sabah 08:00 + akşam 20:00. 26 saat, en uzun boşluğun (20:00 →
        # ertesi 08:00 = 12 sa) iki katından fazla.
        threshold_hours=26,
        sql="SELECT max(generated_at) AS last_at FROM briefings",
        hint="beat'te `briefing-morning`/`briefing-evening` var mı? TZ doğru mu?",
    ),
    Heartbeat(
        key="metrics",
        label="Metrik toplama",
        threshold_hours=48,  # gecelik 23:50; iki tur kaçarsa alarm
        # `computed_at`, `recorded_at` DEĞİL (migration 0008). İkincisi
        # satırın ANLATTIĞI günün etiketidir ve öğleye sabitlenmiştir;
        # nabız olarak okununca yaş negatife düşüyordu (ölçülen: -14,66).
        sql="SELECT max(computed_at) AS last_at FROM metrics",
        hint="beat'te `metrics-rollup-nightly` var mı?",
    ),
    Heartbeat(
        key="purge",
        label="Gövde temizliği",
        threshold_hours=48,  # günlük 03:15; iki tur kaçarsa alarm (Spec §9.3)
        sql=(
            "SELECT max(created_at) AS last_at FROM audit_log "
            "WHERE action = 'purge_expired_bodies'"
        ),
        hint="beat'te `purge-daily` zamanlaması var mı?",
    ),
)


@dataclass(frozen=True)
class StageReport:
    key: str
    label: str
    status: StageStatus
    backlog: int
    oldest_hours: float | None
    threshold_hours: float
    hint: str
    kind: Literal["backlog", "heartbeat"]

    @property
    def is_alarm(self) -> bool:
        return self.status == "red"

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "backlog": self.backlog,
            "oldest_hours": self.oldest_hours,
            "threshold_hours": self.threshold_hours,
            "hint": self.hint,
            "kind": self.kind,
        }


def _classify(age_hours: float | None, threshold: float) -> StageStatus:
    """Yaş → renk. Bekleyen yoksa yeşil; boşluk kanıt değildir."""
    if age_hours is None:
        return "green"
    if age_hours >= threshold:
        return "red"
    if age_hours >= threshold * AMBER_RATIO:
        return "amber"
    return "green"


def stage_report() -> list[StageReport]:
    """Her aşama için birikme ve yaş; en kötü durum başta değil, boru
    hattı sırasında döner — okuyan kişi nerede koptuğunu görsün."""
    out: list[StageReport] = []

    with connection() as conn, conn.cursor() as cur:
        # Toplama nabzı boru hattının başında; sırayı korumak için önce.
        ingest, rest = HEARTBEATS[0], HEARTBEATS[1:]
        out.append(_heartbeat_report(cur, ingest))

        for stage in STAGES:
            cur.execute(stage.sql, stage.get_params())
            row = cur.fetchone() or {}
            backlog = int(row.get("backlog") or 0)
            oldest = row.get("oldest_hours")
            oldest_hours = round(float(oldest), 2) if oldest is not None else None
            out.append(
                StageReport(
                    key=stage.key,
                    label=stage.label,
                    status=_classify(oldest_hours, stage.threshold_hours),
                    backlog=backlog,
                    oldest_hours=oldest_hours,
                    threshold_hours=stage.threshold_hours,
                    hint=stage.hint,
                    kind="backlog",
                )
            )

        for beat in rest:
            out.append(_heartbeat_report(cur, beat))

    return out


def _heartbeat_report(cur: Any, beat: Heartbeat) -> StageReport:
    cur.execute(beat.sql)
    row = cur.fetchone() or {}
    last_at = row.get("last_at")

    if last_at is None:
        # Hiç üretilmemiş: henüz kurulmuş bir sistemde bu normaldir, ama
        # sessizce yeşil göstermek de doğru değil. Sarı: "bakılmalı".
        return StageReport(
            key=beat.key,
            label=beat.label,
            status="amber",
            backlog=0,
            oldest_hours=None,
            threshold_hours=beat.threshold_hours,
            hint=f"Hiç kayıt yok. {beat.hint}",
            kind="heartbeat",
        )

    from datetime import UTC, datetime

    last_at = last_at.replace(tzinfo=UTC) if last_at.tzinfo is None else last_at.astimezone(UTC)

    # Gelecek tarihli kayıt bir NABIZ DEĞİLDİR. Negatif yaş panoda anlamsız
    # bir sayı gösterir ve "çok taze" gibi okunur; oysa kaynağı ya saat
    # kayması ya da yanlış sütundur (migration 0008: `recorded_at` bir gün
    # etiketiydi ve öğleye sabitlendiği için ileri düşüyordu). Sıfıra
    # kırpıyoruz: gösterge yalan söylemesin.
    age = (datetime.now(UTC) - last_at).total_seconds() / 3600
    age_hours = round(max(age, 0.0), 2)
    return StageReport(
        key=beat.key,
        label=beat.label,
        status=_classify(age_hours, beat.threshold_hours),
        backlog=0,
        oldest_hours=age_hours,
        threshold_hours=beat.threshold_hours,
        hint=beat.hint,
        kind="heartbeat",
    )


def alarms() -> list[StageReport]:
    """Yalnızca kırmızı aşamalar."""
    return [r for r in stage_report() if r.is_alarm]


def check_and_log() -> list[dict[str, Any]]:
    """Celery görevinin çağırdığı giriş noktası.

    Kırmızı aşamaları `log.error` ile bildirir. Log seviyesi bilinçli:
    Sentry `error` seviyesini yakalar, `warning`'i yakalamaz — sessiz
    kopmanın sessiz kalmaması bu alarmın tek işidir.
    """
    red = alarms()
    if red:
        log.error(
            "pipeline_stage_broken",
            stages=[r.key for r in red],
            detail=[
                f"{r.label}: {r.backlog} bekliyor, en eskisi {r.oldest_hours} sa "
                f"(eşik {r.threshold_hours} sa)"
                if r.kind == "backlog"
                else f"{r.label}: {r.oldest_hours} saattir üretim yok (eşik {r.threshold_hours} sa)"
                for r in red
            ],
        )
    else:
        log.info("pipeline_stages_healthy")
    return [r.as_dict() for r in red]
