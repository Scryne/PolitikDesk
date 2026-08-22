"""Makro ekonomik anomali uyarıları ve webhook dağıtıcısı (Macro Anomaly Alerting).

TCMB, TÜİK, Hazine ve EVDS serilerindeki istatistiksel anomaliler için
Discord, Slack veya REST webhook uçlarına bildirim formatlar ve iletir.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from politikdesk.analysis.anomaly import evaluate_series
from politikdesk.db import connection
from politikdesk.ingestion.http import HttpClient
from politikdesk.observability import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class MacroAnomalyAlert:
    """Tek bir makro ekonomik anomali uyarısı."""

    alert_id: str
    series_key: str
    series_label: str
    current_value: float
    previous_value: float | None
    change_pct: float | None
    severity: str
    score: float
    detected_at: str
    summary: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def format_alert_payload(
    alert: MacroAnomalyAlert, format_type: str = "generic"
) -> dict[str, Any]:
    """Uyarıyı hedef webhook formatına çevirir (generic, discord, slack)."""
    if format_type == "discord":
        color = 0xE74C3C if alert.severity in {"high", "critical"} else 0xE67E22
        return {
            "embeds": [
                {
                    "title": f"🚨 Makro Anomali: {alert.series_label}",
                    "description": alert.summary,
                    "color": color,
                    "fields": [
                        {
                            "name": "Mevcut Değer",
                            "value": f"{alert.current_value:.2f}",
                            "inline": True,
                        },
                        {"name": "Şiddet", "value": alert.severity.upper(), "inline": True},
                        {"name": "Skor (Sapma)", "value": f"{alert.score:.2f}σ", "inline": True},
                        {
                            "name": "Değişim",
                            "value": (
                                f"%{alert.change_pct:+.2f}"
                                if alert.change_pct is not None
                                else "—"
                            ),
                            "inline": True,
                        },
                    ],
                    "timestamp": alert.detected_at,
                    "footer": {"text": "PolitikDesk Macro Intelligence"},
                }
            ]
        }

    if format_type == "slack":
        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨 Makro Anomali: {alert.series_label}",
                    },
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": alert.summary},
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Mevcut:* {alert.current_value:.2f}"},
                        {"type": "mrkdwn", "text": f"*Şiddet:* {alert.severity.upper()}"},
                        {"type": "mrkdwn", "text": f"*Sapma:* {alert.score:.2f}σ"},
                    ],
                },
            ]
        }

    return {
        "event": "macro_anomaly_alert",
        "alert": alert.as_dict(),
    }


def dispatch_anomaly_alert(
    alert: MacroAnomalyAlert,
    webhook_url: str,
    *,
    format_type: str = "generic",
    http_client: HttpClient | None = None,
) -> bool:
    """Anomali uyarısını belirtilen webhook URL'sine POST eder (SSRF korumalı)."""
    if not webhook_url:
        return False

    from politikdesk.ingestion.http import UnsafeUrlError, validate_url

    try:
        validated_url = validate_url(webhook_url, resolve_dns=True)
    except UnsafeUrlError as err:
        log.warning(
            "anomaly_alert_ssrf_blocked",
            alert_id=alert.alert_id,
            url=webhook_url,
            error=str(err),
        )
        return False

    payload = format_alert_payload(alert, format_type=format_type)

    client = http_client or HttpClient(
        max_retries=1,
        respect_robots=False,
        enforce_ssrf=True,
        resolve_dns=True,
        timeout=5.0,
        user_agent="PolitikDesk-Alerts/1.0",
    )

    try:
        response = client.post(
            validated_url,
            json=payload,
            headers={"Content-Type": "application/json", "User-Agent": "PolitikDesk-Alerts/1.0"},
            source_slug="anomaly-webhook",
        )
        if response.status_code in {200, 204}:
            log.info(
                "anomaly_alert_dispatched",
                alert_id=alert.alert_id,
                series=alert.series_key,
                status=response.status_code,
            )
            return True
        log.warning(
            "anomaly_alert_webhook_bad_status",
            alert_id=alert.alert_id,
            status=response.status_code,
        )
        return False
    except Exception as exc:
        log.warning("anomaly_alert_dispatch_failed", alert_id=alert.alert_id, error=str(exc))
        return False
    finally:
        if http_client is None:
            client.close()


def collect_recent_anomalies() -> list[MacroAnomalyAlert]:
    """Veritabanındaki aktif indikatör serilerini tarayıp tespit edilen anomalileri döner."""
    alerts: list[MacroAnomalyAlert] = []

    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, metric, series_code FROM indicator_series ORDER BY id")
            series_rows = cur.fetchall()

        for r in series_rows:
            series_id = r["id"]
            metric = r["metric"]
            code = r["series_code"]
            det = evaluate_series(series_id)

            if det.state == "anomalous":
                curr = det.observed_value
                prev = det.expected_value
                chg = det.deviation_ratio

                alert_seed = f"{code}:{curr}:{det.method}"
                alert_id = hashlib.sha256(alert_seed.encode("utf-8")).hexdigest()[:12]

                summary = (
                    f"{metric} ({code}) serisinde {det.severity or 'medium'} "
                    f"şiddetinde anomali tespit edildi. "
                    f"Gözlem: {curr:.2f}, Sapma: {det.deviation_ratio or 0.0:.2f}σ "
                    f"({det.reason})."
                )

                alerts.append(
                    MacroAnomalyAlert(
                        alert_id=alert_id,
                        series_key=code,
                        series_label=metric,
                        current_value=curr,
                        previous_value=prev,
                        change_pct=chg,
                        severity=det.severity or "medium",
                        score=abs(det.deviation_ratio or 0.0),
                        detected_at=datetime.now(UTC).isoformat(),
                        summary=summary,
                    )
                )
    except Exception as exc:
        log.warning("collect_recent_anomalies_failed", error=str(exc))

    return alerts
