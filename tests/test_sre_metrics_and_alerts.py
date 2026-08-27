"""Site Reliability Engineering (SRE) telemetrisi ve operasyonel uyarı testleri."""

from __future__ import annotations

from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.sre_metrics import (
    BackupDRStatus,
    CircuitSummary,
    LLMBudgetStatus,
    PipelineSummary,
    QueueDepth,
    SRESnapshot,
    evaluate_alert_rules,
    get_sre_snapshot,
)


def _make_snapshot(
    *,
    celery_default: int = 0,
    celery_llm: int = 0,
    open_circuits: list[str] | None = None,
    daily_spent: float = 1.0,
    daily_budget: float = 10.0,
    backup_age: float | None = 2.0,
    drill_age: float | None = 24.0,
    backup_healthy: bool = True,
    drill_healthy: bool = True,
    green_count: int = 12,
    amber_count: int = 0,
    red_count: int = 0,
    red_stages: list[str] | None = None,
    amber_stages: list[str] | None = None,
) -> SRESnapshot:
    open_c = open_circuits or []
    red_s = red_stages or []
    amber_s = amber_stages or []
    ratio = daily_spent / daily_budget if daily_budget > 0 else 0.0

    return SRESnapshot(
        timestamp="2026-08-23T12:00:00Z",
        queues=QueueDepth(
            celery_default=celery_default,
            celery_llm=celery_llm,
            total=celery_default + celery_llm,
        ),
        circuits=CircuitSummary(
            total_circuits=10,
            open_circuits=open_c,
            half_open_circuits=[],
            is_healthy=len(open_c) == 0,
        ),
        llm_budget=LLMBudgetStatus(
            daily_budget_usd=daily_budget,
            daily_spent_usd=daily_spent,
            spent_ratio=ratio,
            is_exceeded=ratio >= 1.0,
            is_warning=ratio >= 0.8,
        ),
        backup_dr=BackupDRStatus(
            last_backup_hours=backup_age,
            last_drill_hours=drill_age,
            backup_healthy=backup_healthy,
            drill_healthy=drill_healthy,
        ),
        pipeline=PipelineSummary(
            green_count=green_count,
            amber_count=amber_count,
            red_count=red_count,
            red_stages=red_s,
            amber_stages=amber_s,
        ),
    )


# ===========================================================================
# 1. Uyarı Kural Motoru Testleri (evaluate_alert_rules)
# ===========================================================================
def test_nominal_system_generates_info_alert() -> None:
    """Tüm bileşenler sağlıklıyken sistem tek bir INFO 'Tüm Sistemler Nominal' üretir."""
    snapshot = _make_snapshot()
    alerts = evaluate_alert_rules(snapshot)
    assert len(alerts) == 1
    assert alerts[0].severity == "INFO"
    assert "Nominal" in alerts[0].title


def test_multiple_red_stages_triggers_critical_alert() -> None:
    """İki veya daha fazla kırmızı aşama CRITICAL alarm tetikler."""
    snapshot = _make_snapshot(
        red_count=2, red_stages=["Embedding (embed)", "Olay kümeleme (cluster)"]
    )
    alerts = evaluate_alert_rules(snapshot)
    crit = next((a for a in alerts if a.severity == "CRITICAL" and a.source == "pipeline"), None)
    assert crit is not None
    assert "Çoklu Aşama Kesintisi" in crit.title
    assert "drain_pipeline" in crit.action


def test_single_red_stage_triggers_warning_alert() -> None:
    """Tek bir kırmızı aşama WARNING alarm tetikler."""
    snapshot = _make_snapshot(red_count=1, red_stages=["İddia çıkarımı (claims)"])
    alerts = evaluate_alert_rules(snapshot)
    warn = next((a for a in alerts if a.severity == "WARNING" and a.source == "pipeline"), None)
    assert warn is not None
    assert "Boru Hattı Aşama Birikmesi" in warn.title


def test_queue_explosion_triggers_critical_alert() -> None:
    """Kuyruk toplamı 500'ü aştığında CRITICAL queue alarmı tetiklenir."""
    snapshot = _make_snapshot(celery_default=400, celery_llm=150)
    alerts = evaluate_alert_rules(snapshot)
    crit = next((a for a in alerts if a.severity == "CRITICAL" and a.source == "queue"), None)
    assert crit is not None
    assert "Kuyruk Patlaması" in crit.title


def test_high_queue_depth_triggers_warning_alert() -> None:
    """Kuyruk toplamı 100-500 aralığındayken WARNING queue alarmı tetiklenir."""
    snapshot = _make_snapshot(celery_default=80, celery_llm=30)
    alerts = evaluate_alert_rules(snapshot)
    warn = next((a for a in alerts if a.severity == "WARNING" and a.source == "queue"), None)
    assert warn is not None
    assert "Kuyruk Derinliği Yüksek" in warn.title


def test_llm_budget_exceeded_triggers_critical_alert() -> None:
    """Bütçe %100 aşıldığında CRITICAL llm_budget alarmı tetiklenir."""
    snapshot = _make_snapshot(daily_spent=11.0, daily_budget=10.0)
    alerts = evaluate_alert_rules(snapshot)
    crit = next((a for a in alerts if a.severity == "CRITICAL" and a.source == "llm_budget"), None)
    assert crit is not None
    assert "Bütçesi Tükendi" in crit.title


def test_llm_budget_warning_triggers_warning_alert() -> None:
    """Bütçe %80-%99 aralığındayken WARNING llm_budget alarmı tetiklenir."""
    snapshot = _make_snapshot(daily_spent=8.5, daily_budget=10.0)
    alerts = evaluate_alert_rules(snapshot)
    warn = next((a for a in alerts if a.severity == "WARNING" and a.source == "llm_budget"), None)
    assert warn is not None
    assert "Bütçesi Yaklaşıyor" in warn.title


def test_open_circuit_triggers_warning_alert() -> None:
    """Açık bir devre kesici varsa WARNING circuit alarmı tetiklenir."""
    snapshot = _make_snapshot(open_circuits=["https://twitter-bridge.local"])
    alerts = evaluate_alert_rules(snapshot)
    warn = next(
        (a for a in alerts if a.severity == "WARNING" and a.source == "circuit_breaker"), None
    )
    assert warn is not None
    assert "Devre Kesicisi Açık" in warn.title


def test_backup_missing_triggers_critical_alert() -> None:
    """Yedekleme sağlıksızsa CRITICAL backup alarmı tetiklenir."""
    snapshot = _make_snapshot(backup_healthy=False, backup_age=40.0)
    alerts = evaluate_alert_rules(snapshot)
    crit = next((a for a in alerts if a.severity == "CRITICAL" and a.source == "backup"), None)
    assert crit is not None
    assert "Yedekleme Gecikti" in crit.title


def test_drill_overdue_triggers_warning_alert() -> None:
    """DR tatbikatı gecikmişse WARNING recovery_drill alarmı tetiklenir."""
    snapshot = _make_snapshot(drill_healthy=False, drill_age=200.0)
    alerts = evaluate_alert_rules(snapshot)
    warn = next(
        (a for a in alerts if a.severity == "WARNING" and a.source == "recovery_drill"), None
    )
    assert warn is not None
    assert "Tatbikatı Zamanı Geçti" in warn.title


# ===========================================================================
# 2. SRE Anlık Görüntü (Snapshot) Testleri
# ===========================================================================
def test_get_sre_snapshot_runs_safely() -> None:
    """get_sre_snapshot tüm alt modülleri güvenle toplar ve nesne döner."""
    snapshot = get_sre_snapshot()
    assert isinstance(snapshot, SRESnapshot)
    assert snapshot.timestamp
    assert isinstance(snapshot.queues, QueueDepth)
    assert isinstance(snapshot.circuits, CircuitSummary)
    assert isinstance(snapshot.llm_budget, LLMBudgetStatus)
    assert isinstance(snapshot.backup_dr, BackupDRStatus)
    assert isinstance(snapshot.pipeline, PipelineSummary)


# ===========================================================================
# 3. API Uç Nokta Testleri (/admin/sre ve /admin/circuits)
# ===========================================================================
def test_admin_sre_endpoint() -> None:
    """GET /admin/sre JSON sözleşmesini doğrular."""
    client = TestClient(app)
    resp = client.get("/admin/sre")
    assert resp.status_code == 200
    data = resp.json()
    assert "snapshot" in data
    assert "alerts" in data
    assert "beat_schedule" in data
    assert isinstance(data["alerts"], list)
    assert isinstance(data["beat_schedule"], list)


def test_admin_circuits_endpoint() -> None:
    """GET /admin/circuits devre kesici listesi döner."""
    client = TestClient(app)
    resp = client.get("/admin/circuits")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_beat_schedule_summary_and_endpoint() -> None:
    """GET /admin/beat-schedule ve get_beat_schedule_summary fonksiyonunu doğrular."""
    from politikdesk.sre_metrics import get_beat_schedule_summary

    summary = get_beat_schedule_summary()
    assert len(summary) >= 10
    task_names = {item["task"] for item in summary}
    assert "politikdesk.ingest_all" in task_names
    assert "politikdesk.embed_pending" in task_names
    assert "politikdesk.extract_claims_pending" in task_names

    client = TestClient(app)
    resp = client.get("/admin/beat-schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == len(summary)
