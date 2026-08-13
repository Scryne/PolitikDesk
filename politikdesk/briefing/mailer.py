"""Brifing e-posta gönderimi (F3-17).

**SMTP yapılandırılmamışsa gönderim atlanır, hata verilmez.** Brifing
yine üretilir ve `/briefing/{tarih}` sayfasında görünür. Gerekçe: bir
e-posta sağlayıcısının yokluğu bir *dağıtım* eksiğidir; üretim hattını
durdurması için bir sebep değildir. Atlanan gönderim `send_error`
alanına yazılır ki pano "gönderilmedi" ile "gönderilemedi"yi ayırsın.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

from politikdesk.config import Settings, get_settings
from politikdesk.db import connection
from politikdesk.observability import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class SendResult:
    sent: bool
    skipped_reason: str = ""
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"sent": self.sent, "skipped_reason": self.skipped_reason, "error": self.error}


def is_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.smtp_host and (settings.smtp_from or settings.smtp_user))


def build_message(
    *, subject: str, to: str, html_body: str, text_body: str, sender: str
) -> EmailMessage:
    """`multipart/alternative`: düz metin önce, HTML alternatif olarak."""
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    return message


def _send_smtp(message: EmailMessage, settings: Settings) -> None:
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


def send_notification(
    *, subject: str, text_body: str, html_body: str = "",
    settings: Settings | None = None,
) -> SendResult:
    """Brifing dışı operasyonel bildirim gönderir (F4-07 bütçe alarmı).

    Brifing gönderimiyle aynı sözleşme: **SMTP yoksa hata değil, atlama.**
    Bir alarmın e-postayla ulaşamaması, alarmın kendisini geçersiz
    kılmaz — çağıran zaten loga ve denetim izine yazmıştır.
    """
    settings = settings or get_settings()

    if not is_configured(settings):
        return SendResult(False, skipped_reason="smtp_unconfigured")

    message = build_message(
        subject=subject,
        to=settings.user_email,
        html_body=html_body or f"<pre>{text_body}</pre>",
        text_body=text_body,
        sender=settings.smtp_from or settings.smtp_user,
    )

    try:
        _send_smtp(message, settings)
    except Exception as exc:  # noqa: BLE001 — bildirim hatası hattı durdurmaz
        detail = f"{type(exc).__name__}: {str(exc)[:200]}"
        log.warning("notification_send_failed", subject=subject, detail=detail)
        return SendResult(False, error=detail)

    log.info("notification_sent", subject=subject, to=settings.user_email)
    return SendResult(True)


def send_briefing(briefing_id: int, *, settings: Settings | None = None) -> SendResult:
    """Kaydedilmiş brifingi e-postayla gönderir ve sonucu işler."""
    settings = settings or get_settings()

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT b.id, b.briefing_date, b.slot, b.body_html, b.body_text,
                   b.sent_at, u.email
            FROM briefings b JOIN users u ON u.id = b.user_id
            WHERE b.id = %s
            """,
            (briefing_id,),
        )
        row = cur.fetchone()

    if row is None:
        return SendResult(False, error=f"Brifing yok: {briefing_id}")
    if row["sent_at"] is not None:
        return SendResult(False, skipped_reason="already_sent")

    if not is_configured(settings):
        _record(briefing_id, sent=False, error="SMTP yapılandırılmadı (PD_SMTP_HOST boş)")
        log.info("briefing_send_skipped", briefing_id=briefing_id, reason="smtp_unconfigured")
        return SendResult(False, skipped_reason="smtp_unconfigured")

    from politikdesk.briefing.generator import SLOT_LABELS

    subject = f"{SLOT_LABELS[row['slot']]} — {row['briefing_date']:%d.%m.%Y}"
    message = build_message(
        subject=subject,
        to=row["email"],
        html_body=row["body_html"],
        text_body=row["body_text"],
        sender=settings.smtp_from or settings.smtp_user,
    )

    try:
        _send_smtp(message, settings)
    except Exception as exc:  # noqa: BLE001 — gönderim hatası hattı durdurmaz
        detail = f"{type(exc).__name__}: {str(exc)[:200]}"
        _record(briefing_id, sent=False, error=detail)
        log.warning("briefing_send_failed", briefing_id=briefing_id, detail=detail)
        return SendResult(False, error=detail)

    _record(briefing_id, sent=True, error=None)
    log.info("briefing_sent", briefing_id=briefing_id, to=row["email"])
    return SendResult(True)


def _record(briefing_id: int, *, sent: bool, error: str | None) -> None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE briefings
            SET sent_at = CASE WHEN %s THEN now() ELSE sent_at END,
                send_error = %s
            WHERE id = %s
            """,
            (sent, error, briefing_id),
        )
        conn.commit()
