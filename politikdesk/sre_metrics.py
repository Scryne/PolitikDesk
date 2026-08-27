"""Site Reliability Engineering (SRE) ve operasyonel gözlemlenebilirlik katmanı (Phases 2-4).

Bu modül ağır harici altyapı bağımlılığı olmadan:
  1. Celery/Redis kuyruk derinliklerini (`celery`, `llm`),
  2. Devre kesici (Circuit Breaker) durumlarını,
  3. LLM bütçe ve sağlayıcı hata metriklerini,
  4. Yedekleme ve Felaket Kurtarma (DR) tazeliğini,
  5. Boru hattı aşama ve nabız özetlerini,
  6. Eyleme dönük (action-oriented) uyarı kurallarını (CRITICAL, WARNING, INFO)
tek bir anlık görüntüde (snapshot) birleştirir ve değerlendirir.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from politikdesk.config import get_settings
from politikdesk.observability import get_logger

log = get_logger(__name__)

AlertSeverity = Literal["CRITICAL", "WARNING", "INFO"]


@dataclass(frozen=True)
class Alert:
    """Operatöre doğrudan aksiyon veren yapılandırılmış sistem uyarısı."""

    severity: AlertSeverity
    title: str
    detail: str
    action: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QueueDepth:
    celery_default: int
    celery_llm: int
    total: int


@dataclass(frozen=True)
class CircuitSummary:
    total_circuits: int
    open_circuits: list[str]
    half_open_circuits: list[str]
    is_healthy: bool


@dataclass(frozen=True)
class LLMBudgetStatus:
    daily_budget_usd: float
    daily_spent_usd: float
    spent_ratio: float
    is_exceeded: bool
    is_warning: bool


@dataclass(frozen=True)
class BackupDRStatus:
    last_backup_hours: float | None
    last_drill_hours: float | None
    backup_healthy: bool
    drill_healthy: bool


@dataclass(frozen=True)
class PipelineSummary:
    green_count: int
    amber_count: int
    red_count: int
    red_stages: list[str]
    amber_stages: list[str]


@dataclass(frozen=True)
class SRESnapshot:
    """Tüm platformun operasyonel anlık durum özeti."""

    timestamp: str
    queues: QueueDepth
    circuits: CircuitSummary
    llm_budget: LLMBudgetStatus
    backup_dr: BackupDRStatus
    pipeline: PipelineSummary

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "queues": asdict(self.queues),
            "circuits": asdict(self.circuits),
            "llm_budget": asdict(self.llm_budget),
            "backup_dr": asdict(self.backup_dr),
            "pipeline": asdict(self.pipeline),
        }


# ---------------------------------------------------------------- snapshot
def get_redis_client() -> Any:
    """Redis bağlantı istemcisi oluşturur (hata durumunda None döner)."""
    try:
        import redis

        return redis.from_url(get_settings().redis_url, socket_timeout=2.0)
    except Exception as exc:  # noqa: BLE001
        log.debug("redis_client_init_failed", error=str(exc))
        return None


def get_queue_depths() -> QueueDepth:
    """Redis üzerinden Celery kuyruk derinliklerini okur."""
    try:
        client = get_redis_client()
        if client is None:
            return QueueDepth(celery_default=0, celery_llm=0, total=0)
        default_len = int(client.llen("celery") or 0)
        llm_len = int(client.llen("llm") or 0)
        return QueueDepth(
            celery_default=default_len,
            celery_llm=llm_len,
            total=default_len + llm_len,
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("queue_depth_read_failed", error=str(exc))
        return QueueDepth(celery_default=0, celery_llm=0, total=0)


def get_circuit_summary() -> CircuitSummary:
    """Devre kesicilerin durum özetini derler."""
    try:
        from politikdesk.ingestion.circuit import get_all_circuit_metrics

        metrics = get_all_circuit_metrics()
        open_list = [m["host"] for m in metrics if m["state"] == "open"]
        half_open_list = [m["host"] for m in metrics if m["state"] == "half_open"]
        return CircuitSummary(
            total_circuits=len(metrics),
            open_circuits=open_list,
            half_open_circuits=half_open_list,
            is_healthy=len(open_list) == 0,
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("circuit_summary_read_failed", error=str(exc))
        return CircuitSummary(
            total_circuits=0,
            open_circuits=[],
            half_open_circuits=[],
            is_healthy=True,
        )


def get_llm_budget_status() -> LLMBudgetStatus:
    """Günlük LLM bütçe kullanımını sorgular."""
    try:
        from politikdesk.llm.budget import BudgetGuard

        guard = BudgetGuard()
        daily_spent = float(guard.ledger.spent_today_usd())
        daily_budget = float(guard.settings.llm_daily_budget_usd)
        ratio = (daily_spent / daily_budget) if daily_budget > 0 else 0.0
        return LLMBudgetStatus(
            daily_budget_usd=daily_budget,
            daily_spent_usd=daily_spent,
            spent_ratio=ratio,
            is_exceeded=ratio >= 1.0,
            is_warning=ratio >= 0.8,
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("llm_budget_status_read_failed", error=str(exc))
        return LLMBudgetStatus(
            daily_budget_usd=10.0,
            daily_spent_usd=0.0,
            spent_ratio=0.0,
            is_exceeded=False,
            is_warning=False,
        )


def get_backup_dr_status() -> BackupDRStatus:
    """Yedekleme ve kurtarma tatbikatı tazelik durumunu sorgular."""
    try:
        from politikdesk.pipeline_health import stage_report

        reports = stage_report()
        backup_rep = next((r for r in reports if r.key == "backup"), None)
        drill_rep = next((r for r in reports if r.key == "recovery_drill"), None)

        b_age = backup_rep.oldest_hours if backup_rep else None
        d_age = drill_rep.oldest_hours if drill_rep else None

        b_ok = backup_rep.status == "green" if backup_rep else True
        d_ok = drill_rep.status == "green" if drill_rep else True

        return BackupDRStatus(
            last_backup_hours=b_age,
            last_drill_hours=d_age,
            backup_healthy=b_ok,
            drill_healthy=d_ok,
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("backup_dr_status_read_failed", error=str(exc))
        return BackupDRStatus(
            last_backup_hours=None,
            last_drill_hours=None,
            backup_healthy=True,
            drill_healthy=True,
        )


def get_pipeline_summary() -> PipelineSummary:
    """Boru hattı aşamalarının renk ve birikme özetini derler."""
    try:
        from politikdesk.pipeline_health import stage_report

        reports = stage_report()
        green = sum(1 for r in reports if r.status == "green")
        amber = sum(1 for r in reports if r.status == "amber")
        red = sum(1 for r in reports if r.status == "red")
        red_keys = [f"{r.label} ({r.key})" for r in reports if r.status == "red"]
        amber_keys = [f"{r.label} ({r.key})" for r in reports if r.status == "amber"]

        return PipelineSummary(
            green_count=green,
            amber_count=amber,
            red_count=red,
            red_stages=red_keys,
            amber_stages=amber_keys,
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("pipeline_summary_read_failed", error=str(exc))
        return PipelineSummary(
            green_count=0,
            amber_count=0,
            red_count=0,
            red_stages=[],
            amber_stages=[],
        )


def get_sre_snapshot() -> SRESnapshot:
    """Tüm sistem operasyonel metriklerinin anlık görüntüsünü üretir."""
    return SRESnapshot(
        timestamp=datetime.now(UTC).isoformat(),
        queues=get_queue_depths(),
        circuits=get_circuit_summary(),
        llm_budget=get_llm_budget_status(),
        backup_dr=get_backup_dr_status(),
        pipeline=get_pipeline_summary(),
    )


def get_beat_schedule_summary() -> list[dict[str, Any]]:
    """Celery Beat zamanlanmış periyodik görevlerinin dökümünü döner."""
    try:
        from politikdesk.worker import app as celery_app

        schedule_dict = getattr(celery_app.conf, "beat_schedule", {})
        task_routes = getattr(celery_app.conf, "task_routes", {}) or {}

        summary: list[dict[str, Any]] = []
        for name, entry in schedule_dict.items():
            task_name = entry.get("task", "")
            sched = entry.get("schedule")
            options = entry.get("options") or {}

            if isinstance(sched, int | float):
                sched_desc = (
                    f"{int(sched)} sn ({int(sched)//60} dk)"
                    if sched >= 60
                    else f"{sched} sn"
                )
                is_crontab = False
            else:
                sched_desc = str(sched)
                is_crontab = True

            route_info = task_routes.get(task_name, {})
            queue_name = route_info.get("queue", "celery")

            summary.append({
                "name": name,
                "task": task_name,
                "schedule_desc": sched_desc,
                "is_crontab": is_crontab,
                "queue": queue_name,
                "expires": options.get("expires"),
            })
        return summary
    except Exception as exc:  # noqa: BLE001
        log.debug("beat_schedule_summary_failed", error=str(exc))
        return []


# ----------------------------------------------------------- alert evaluation
def evaluate_alert_rules(snapshot: SRESnapshot) -> list[Alert]:
    """Anlık metrik görüntüsünü eyleme dönük kural motorundan geçirir."""
    alerts: list[Alert] = []

    # 1. Pipeline Alarm Kuralları
    if snapshot.pipeline.red_count >= 2:
        alerts.append(
            Alert(
                severity="CRITICAL",
                title="Boru Hattı Çoklu Aşama Kesintisi",
                detail=(
                    f"{snapshot.pipeline.red_count} aşama kırmızı alarm veriyor: "
                    f"{', '.join(snapshot.pipeline.red_stages)}"
                ),
                action=(
                    "İşçileri ve bağımlılıkları kontrol edin: `docker compose ps` "
                    "ve `python -m scripts.drain_pipeline`"
                ),
                source="pipeline",
            )
        )
    elif snapshot.pipeline.red_count == 1:
        alerts.append(
            Alert(
                severity="WARNING",
                title="Boru Hattı Aşama Birikmesi",
                detail=f"1 aşama kırmızı alarm veriyor: {', '.join(snapshot.pipeline.red_stages)}",
                action="Aşama sağlığı panosunu inceleyin: `/admin/pipeline-health`",
                source="pipeline",
            )
        )

    # 2. Kuyruk Birikme Kuralları
    if snapshot.queues.total > 500:
        alerts.append(
            Alert(
                severity="CRITICAL",
                title="Celery Kuyruk Patlaması (Queue Explosion)",
                detail=(
                    f"Redis kuyruklarında toplam {snapshot.queues.total} bekleyen görev var "
                    f"(default: {snapshot.queues.celery_default}, "
                    f"llm: {snapshot.queues.celery_llm})"
                ),
                action=(
                    "Worker loglarını inceleyin ve eşzamanlılığı artırın: "
                    "`docker compose logs --tail 100 worker`"
                ),
                source="queue",
            )
        )
    elif snapshot.queues.total > 100:
        alerts.append(
            Alert(
                severity="WARNING",
                title="Celery Kuyruk Derinliği Yüksek",
                detail=f"Redis kuyruklarında {snapshot.queues.total} görev işleme bekliyor.",
                action="Boru hattı akış hızını izleyin: `/admin/pipeline-health`",
                source="queue",
            )
        )

    # 3. LLM Bütçe Kuralları
    if snapshot.llm_budget.is_exceeded:
        alerts.append(
            Alert(
                severity="CRITICAL",
                title="Günlük LLM Bütçesi Tükendi",
                detail=(
                    f"Harcama: ${snapshot.llm_budget.daily_spent_usd:.2f} / "
                    f"${snapshot.llm_budget.daily_budget_usd:.2f} "
                    f"(%{snapshot.llm_budget.spent_ratio * 100:.1f})"
                ),
                action=(
                    "LLM çağrıları durduruldu. Gerekliyse `.env` içinde "
                    "`PD_LLM_DAILY_BUDGET_USD` artırın."
                ),
                source="llm_budget",
            )
        )
    elif snapshot.llm_budget.is_warning:
        alerts.append(
            Alert(
                severity="WARNING",
                title="Günlük LLM Bütçesi Yaklaşıyor",
                detail=(
                    f"Harcama: ${snapshot.llm_budget.daily_spent_usd:.2f} / "
                    f"${snapshot.llm_budget.daily_budget_usd:.2f} "
                    f"(%{snapshot.llm_budget.spent_ratio * 100:.1f})"
                ),
                action="Bütçe tüketimini izleyin: `/admin/metrics`",
                source="llm_budget",
            )
        )

    # 4. Devre Kesici (Circuit Breaker) Kuralları
    if snapshot.circuits.open_circuits:
        alerts.append(
            Alert(
                severity="WARNING",
                title="Dış Kaynak Devre Kesicisi Açık",
                detail=(
                    f"{len(snapshot.circuits.open_circuits)} kaynak arıza nedeniyle geçici olarak "
                    f"devre dışı: {', '.join(snapshot.circuits.open_circuits)}"
                ),
                action=(
                    "Kaynak bağlantılarını inceleyin: `/admin/health` veya "
                    "`python -m scripts.ingest`"
                ),
                source="circuit_breaker",
            )
        )

    # 5. Yedekleme ve DR Kuralları
    if not snapshot.backup_dr.backup_healthy:
        alerts.append(
            Alert(
                severity="CRITICAL",
                title="Yedekleme Gecikti / Eksik",
                detail=(
                    f"Son başarılı yedek {snapshot.backup_dr.last_backup_hours or 'N/A'} "
                    "saattir alınmadı (eşik: 36 sa)."
                ),
                action="Manuel yedek alın: `python -m scripts.backup create`",
                source="backup",
            )
        )

    if not snapshot.backup_dr.drill_healthy:
        alerts.append(
            Alert(
                severity="WARNING",
                title="Felaket Kurtarma (DR) Tatbikatı Zamanı Geçti",
                detail=(
                    f"Son DR tatbikatı {snapshot.backup_dr.last_drill_hours or 'N/A'} "
                    "saattir yapılmadı (eşik: 168 sa / 7 gün)."
                ),
                action="Otomatik DR tatbikatı yürütün: `python -m scripts.backup drill`",
                source="recovery_drill",
            )
        )

    if not alerts:
        alerts.append(
            Alert(
                severity="INFO",
                title="Tüm Sistemler Nominal",
                detail="Boru hattı, kuyruklar, bütçe, devre kesiciler ve yedekleme sağlıklı.",
                action="Herhangi bir müdahaleye gerek yoktur.",
                source="system",
            )
        )

    return alerts
