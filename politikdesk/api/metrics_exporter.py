"""Prometheus / OpenMetrics Standart Telemetri Exporter (Phases 3-4, SRE).

PolitikDesk sistem metriklerini, kuyruk derinliklerini, aşama birikmelerini,
devre kesici durumlarını ve LLM bütçe tüketimini Prometheus metrik formatında
(text/plain; version=0.0.4) dışa aktarır.
"""

from __future__ import annotations

import time

from politikdesk.pipeline_health import stage_report
from politikdesk.sre_metrics import get_sre_snapshot

_PROCESS_START_TIME = time.time()


def generate_prometheus_metrics() -> str:
    """Tüm sistem telemetrisini Prometheus formatında üretir."""
    lines: list[str] = [
        "# HELP politikdesk_uptime_seconds PolitikDesk sunucu çalışma süresi.",
        "# TYPE politikdesk_uptime_seconds gauge",
        f"politikdesk_uptime_seconds {max(0.0, time.time() - _PROCESS_START_TIME):.2f}",
        "",
    ]

    # 1. SRE Snapshot Metrikleri
    try:
        snap = get_sre_snapshot()
        queue_default = snap.queues.celery_default
        queue_llm = snap.queues.celery_llm
        queue_total = snap.queues.total
        circuits_open = len(snap.circuits.open_circuits)
        circuits_total = snap.circuits.total_circuits
        llm_spent = snap.llm_budget.daily_spent_usd
        llm_budget = snap.llm_budget.daily_budget_usd
        llm_ratio = snap.llm_budget.spent_ratio
        active_alerts = snap.pipeline.red_count + snap.pipeline.amber_count
        backup_age = snap.backup_dr.last_backup_hours or 0.0
        backup_healthy = 1 if snap.backup_dr.backup_healthy else 0
        drill_age = snap.backup_dr.last_drill_hours or 0.0
        drill_healthy = 1 if snap.backup_dr.drill_healthy else 0
    except Exception:  # noqa: BLE001
        queue_default = 0
        queue_llm = 0
        queue_total = 0
        circuits_open = 0
        circuits_total = 0
        llm_spent = 0.0
        llm_budget = 5.0
        llm_ratio = 0.0
        active_alerts = 0
        backup_age = 0.0
        backup_healthy = 1
        drill_age = 0.0
        drill_healthy = 1

    # Kuyruk derinlikleri
    lines.extend([
        "# HELP politikdesk_queue_depth Celery kuyruklarındaki bekleyen görev sayısı.",
        "# TYPE politikdesk_queue_depth gauge",
        f'politikdesk_queue_depth{{queue="celery"}} {queue_default}',
        f'politikdesk_queue_depth{{queue="llm"}} {queue_llm}',
        f'politikdesk_queue_depth{{queue="total"}} {queue_total}',
        "",
    ])

    # Devre kesiciler
    lines.extend([
        "# HELP politikdesk_circuits_open Açık (kesilmiş) kaynak devre kesici sayısı.",
        "# TYPE politikdesk_circuits_open gauge",
        f"politikdesk_circuits_open {circuits_open}",
        "# HELP politikdesk_circuits_total Kayıtlı toplam devre kesici sayısı.",
        "# TYPE politikdesk_circuits_total gauge",
        f"politikdesk_circuits_total {circuits_total}",
        "",
    ])

    # LLM Bütçe
    lines.extend([
        "# HELP politikdesk_llm_budget_used_usd Günlük tüketilen LLM bütçesi (USD).",
        "# TYPE politikdesk_llm_budget_used_usd gauge",
        f"politikdesk_llm_budget_used_usd {llm_spent:.4f}",
        "# HELP politikdesk_llm_budget_limit_usd Günlük azami LLM bütçe tavanı (USD).",
        "# TYPE politikdesk_llm_budget_limit_usd gauge",
        f"politikdesk_llm_budget_limit_usd {llm_budget:.4f}",
        "# HELP politikdesk_llm_budget_ratio Tüketilen bütçe oranı (0.0 - 1.0).",
        "# TYPE politikdesk_llm_budget_ratio gauge",
        f"politikdesk_llm_budget_ratio {llm_ratio:.4f}",
        "",
    ])

    # Yedekleme ve Kurtarma (Backup & DR Freshness)
    lines.extend([
        "# HELP politikdesk_backup_age_hours Son başarılı yedeğin üzerinden geçen saat.",
        "# TYPE politikdesk_backup_age_hours gauge",
        f"politikdesk_backup_age_hours {backup_age:.2f}",
        "# HELP politikdesk_backup_healthy Yedekleme tazelik durumu (1=sağlıklı, 0=eski/arızalı).",
        "# TYPE politikdesk_backup_healthy gauge",
        f"politikdesk_backup_healthy {backup_healthy}",
        "# HELP politikdesk_drill_age_hours Son başarılı DR tatbikatının üzerinden geçen saat.",
        "# TYPE politikdesk_drill_age_hours gauge",
        f"politikdesk_drill_age_hours {drill_age:.2f}",
        "# HELP politikdesk_drill_healthy DR tatbikat tazelik durumu (1=sağlıklı, 0=eski/arızalı).",
        "# TYPE politikdesk_drill_healthy gauge",
        f"politikdesk_drill_healthy {drill_healthy}",
        "",
    ])

    # Uyarı sayısı
    lines.extend([
        "# HELP politikdesk_active_alerts Aktif eyleme dönük sistem uyarıları.",
        "# TYPE politikdesk_active_alerts gauge",
        f"politikdesk_active_alerts {active_alerts}",
        "",
    ])

    # 2. Boru Hattı Aşama Metrikleri
    try:
        stages = stage_report()
    except Exception:  # noqa: BLE001
        stages = []

    lines.extend([
        "# HELP politikdesk_pipeline_stage_backlog Aşamalarda bekleyen öğe sayısı.",
        "# TYPE politikdesk_pipeline_stage_backlog gauge",
    ])
    for s in stages:
        lines.append(f'politikdesk_pipeline_stage_backlog{{stage="{s.key}"}} {s.backlog}')
    lines.append("")

    lines.extend([
        "# HELP politikdesk_pipeline_stage_oldest_hours En eski bekleyen öğenin saati.",
        "# TYPE politikdesk_pipeline_stage_oldest_hours gauge",
    ])
    for s in stages:
        hours = s.oldest_hours if s.oldest_hours is not None else 0.0
        lines.append(f'politikdesk_pipeline_stage_oldest_hours{{stage="{s.key}"}} {hours:.2f}')
    lines.append("")

    lines.extend([
        "# HELP politikdesk_pipeline_stage_status Aşama durumu (1=green, 2=amber, 3=red).",
        "# TYPE politikdesk_pipeline_stage_status gauge",
    ])
    status_map: dict[str, int] = {"green": 1, "amber": 2, "red": 3}
    for s in stages:
        lines.append(
            f'politikdesk_pipeline_stage_status{{stage="{s.key}"}} {status_map.get(s.status, 0)}'
        )
    lines.append("")

    return "\n".join(lines) + "\n"
