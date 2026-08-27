"""SRE & Operasyonel Alarm Webhook Motoru (Discord / Telegram / Slack).

Sistemde oluşan kritik alarmları (boru hattı tıkanması, devre kesici açılması,
LLM bütçe tükenmesi, konteyner çökmesi) operatöre gerçek zamanlı olarak iletir.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from politikdesk.config import get_settings
from politikdesk.observability import get_logger

log = get_logger(__name__)

AlertSeverity = Literal["CRITICAL", "WARNING", "INFO"]

_SEVERITY_COLORS = {
    "CRITICAL": 15682628,  # #EF4444 kırmızı
    "WARNING": 16096779,  # #F59E0B turuncu
    "INFO": 3899990,  # #3B82F6 mavi
}

_SEVERITY_EMOJIS = {
    "CRITICAL": "🚨 [KRİTİK]",
    "WARNING": "⚠️ [UYARI]",
    "INFO": "ℹ️ [BİLGİ]",
}

# Son gönderilen alarmların tekrarını önleyen önbellek (alert_key -> timestamp)
_COOLDOWN_SECONDS = 300  # 5 dakika
_RECENT_ALERTS: dict[str, float] = {}


def format_discord_payload(
    title: str,
    detail: str,
    severity: AlertSeverity,
    source: str,
    action: str,
) -> dict[str, Any]:
    """Discord Webhook için embed yapısı üretir."""
    color = _SEVERITY_COLORS.get(severity, _SEVERITY_COLORS["INFO"])
    prefix = _SEVERITY_EMOJIS.get(severity, "[ALARM]")

    fields = [
        {"name": "Kaynak / Servis", "value": f"`{source}`", "inline": True},
        {"name": "Seviye", "value": f"**{severity}**", "inline": True},
        {"name": "Ayrıntı", "value": detail[:1024] if detail else "Belirtilmedi.", "inline": False},
    ]
    if action:
        fields.append(
            {"name": "Önerilen Aksiyon (Runbook)", "value": f"`{action}`", "inline": False}
        )

    return {
        "username": "PolitikDesk SRE Watchdog",
        "embeds": [
            {
                "title": f"{prefix} {title}",
                "color": color,
                "fields": fields,
                "footer": {"text": "PolitikDesk Otomatik Operasyon Nöbetçisi"},
                "timestamp": datetime.now(UTC).isoformat(),
            }
        ],
    }


def format_slack_payload(
    title: str,
    detail: str,
    severity: AlertSeverity,
    source: str,
    action: str,
) -> dict[str, Any]:
    """Slack Incoming Webhook için Block Kit yapısı üretir."""
    prefix = _SEVERITY_EMOJIS.get(severity, "[ALARM]")
    text_summary = f"{prefix} *{title}* (`{source}`)\n>{detail}"
    if action:
        text_summary += f"\n*Aksiyon:* `{action}`"

    stamp_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    return {
        "text": f"{prefix} {title}",
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text_summary},
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"PolitikDesk SRE | {stamp_str}",
                    }
                ],
            },
        ],
    }


def format_telegram_payload(
    title: str,
    detail: str,
    severity: AlertSeverity,
    source: str,
    action: str,
) -> dict[str, Any]:
    """Telegram Bot API için HTML mesajı üretir."""
    prefix = _SEVERITY_EMOJIS.get(severity, "[ALARM]")
    msg = f"<b>{prefix} {title}</b>\n\n"
    msg += f"<b>Kaynak:</b> <code>{source}</code>\n"
    msg += f"<b>Seviye:</b> {severity}\n"
    msg += f"<b>Ayrıntı:</b> {detail}\n"
    if action:
        msg += f"<b>Aksiyon:</b> <code>{action}</code>\n"
    msg += f"\n<i>PolitikDesk SRE • {datetime.now(UTC).strftime('%H:%M:%S UTC')}</i>"

    return {"text": msg, "parse_mode": "HTML"}


def format_generic_payload(
    title: str,
    detail: str,
    severity: AlertSeverity,
    source: str,
    action: str,
) -> dict[str, Any]:
    """Standart REST JSON webhook yükü."""
    return {
        "service": "politikdesk",
        "title": title,
        "detail": detail,
        "severity": severity,
        "source": source,
        "action": action,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def send_alert_notification(
    title: str,
    detail: str,
    *,
    severity: AlertSeverity = "WARNING",
    source: str = "watchdog",
    action: str = "",
    webhook_url: str | None = None,
    force: bool = False,
) -> bool:
    """Harici bildirim kanalına alarm gönderir.
    
    Cooldown mekanizması sayesinde aynı alarm 5 dakika içinde birden fazla
    kez tekrarlanarak kanalı boğmaz (force=True hariç).
    """
    settings = get_settings()
    url = webhook_url or settings.alert_webhook_url
    if not url or not url.strip():
        log.debug("sre_alert_webhook_not_configured", title=title, severity=severity)
        return False

    url = url.strip()

    # Cooldown kontrolü
    alert_key = f"{source}:{title}:{severity}"
    now = time.time()
    if not force:
        last_sent = _RECENT_ALERTS.get(alert_key, 0.0)
        if now - last_sent < _COOLDOWN_SECONDS:
            log.debug("sre_alert_suppressed_cooldown", key=alert_key, elapsed=now - last_sent)
            return False

    # Platform tespiti ve yük hazırlama
    if "discord.com/api/webhooks" in url:
        payload = format_discord_payload(title, detail, severity, source, action)
    elif "hooks.slack.com" in url:
        payload = format_slack_payload(title, detail, severity, source, action)
    elif "api.telegram.org" in url:
        payload = format_telegram_payload(title, detail, severity, source, action)
    else:
        payload = format_generic_payload(title, detail, severity, source, action)

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code in (200, 204):
                _RECENT_ALERTS[alert_key] = now
                log.info("sre_alert_sent", title=title, severity=severity, status=resp.status_code)
                return True
            log.warning("sre_alert_http_error", status=resp.status_code, body=resp.text[:200])
            return False
    except Exception as exc:
        log.warning("sre_alert_dispatch_failed", error=str(exc), url=url[:30] + "...")
        return False
