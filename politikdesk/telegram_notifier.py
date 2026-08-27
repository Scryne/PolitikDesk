"""Telegram Bot Bildirim Motoru ve Tek Tıkla X Paylaşım Entegrasyonu (Spec §12.4, §15).

Teyit zincirinden geçen ve otomatik olarak tweet taslağı üretilen her yeni gelişmeyi
kullanıcının Telegram hesabına anlık olarak iletir. Mesaj altında doğrudan X (Twitter)
Web Intent paylaşım linki ve PolitikDesk olay detay linki sunar.
"""

from __future__ import annotations

import html
import urllib.parse
from datetime import UTC, datetime
from typing import Any

import httpx

from politikdesk.config import get_settings
from politikdesk.observability import get_logger

log = get_logger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


def _escape_html(text: str) -> str:
    """Telegram HTML ayrıştırıcısı için güvenli metin üretir."""
    if not text:
        return ""
    return html.escape(text, quote=True)


def build_x_intent_url(tweet_text: str) -> str:
    """X (Twitter) Web Intent paylaşım URL'si üretir."""
    base = "https://twitter.com/intent/tweet"
    params = {"text": tweet_text}
    return f"{base}?{urllib.parse.urlencode(params)}"


def format_draft_telegram_message(
    event: dict[str, Any],
    draft: dict[str, Any],
    claims: list[dict[str, Any]] | None = None,
    *,
    public_base_url: str = "http://localhost:8000",
) -> tuple[str, dict[str, Any]]:
    """Telegram mesaj metnini ve inline keyboard butonlarını üretir."""
    event_id = event.get("id", 0)
    title = event.get("title", "Yeni Gelişme")
    salience = event.get("salience_score", 0)
    category = event.get("category", "Gündem").capitalize()
    
    # Kanıt & İddia durumu
    is_verified = event.get("status") in ("ready", "strongly_corroborated")
    evidence_status = "🟢 Doğrulandı" if is_verified else "🟡 İnceleniyor"
    if claims:
        verified_count = sum(
            1
            for c in claims
            if c.get("evidence_status") in ("strongly_corroborated", "partially_corroborated")
        )
        claims_summary = f"{verified_count}/{len(claims)} teyitli iddia"
    else:
        claims_summary = "Teyitli veriler mevcut"

    draft_body = draft.get("body", "")

    # HTML Biçimlendirme
    score_line = (
        f"⭐ <b>Gündem Skoru:</b> {salience}/90 · "
        f"<b>Durum:</b> {evidence_status} ({claims_summary})"
    )
    msg = (
        f"🚨 <b>YENİ DOĞRULANMIŞ GELİŞME</b> | <i>{_escape_html(category)}</i>\n\n"
        f"📌 <b>{_escape_html(title)}</b>\n"
        f"{score_line}\n\n"
        f"✍️ <b>Hazır X (Twitter) Tweeti:</b>\n"
        f"<code>{_escape_html(draft_body)}</code>\n\n"
        f"⏱ <i>PolitikDesk Editoryal Masası • {datetime.now(UTC).strftime('%H:%M:%S UTC')}</i>"
    )

    # Butonlar
    x_url = build_x_intent_url(draft_body)
    row_buttons: list[dict[str, str]] = [
        {"text": "🚀 X'te Aç ve Paylaş", "url": x_url}
    ]

    # Telegram API kuralı: Inline keyboard butonlarında localhost / 127.0.0.1 linklerini
    # 'Wrong HTTP URL' gerekçesiyle reddeder. Yalnızca geçerli genel alan adlarında ekle.
    is_local = any(loc in public_base_url.lower() for loc in ("localhost", "127.0.0.1", "0.0.0.0"))
    if not is_local and public_base_url.startswith(("http://", "https://")):
        event_url = f"{public_base_url.rstrip('/')}/event/{event_id}"
        row_buttons.append({"text": "📊 Olayı İncele", "url": event_url})

    reply_markup = {
        "inline_keyboard": [row_buttons]
    }

    return msg, reply_markup


def send_draft_notification(
    event: dict[str, Any],
    draft: dict[str, Any],
    claims: list[dict[str, Any]] | None = None,
    *,
    bot_token: str | None = None,
    chat_id: str | None = None,
    public_base_url: str | None = None,
    timeout: float = 10.0,
) -> bool:
    """Üretilen taslağı Telegram Bot API üzerinden kullanıcıya gönderir."""
    settings = get_settings()
    token = (settings.telegram_bot_token if bot_token is None else bot_token).strip()
    target_chat = (settings.telegram_chat_id if chat_id is None else chat_id).strip()
    base_url = public_base_url or settings.public_base_url

    if not token or not target_chat:
        log.debug("telegram_notification_skipped", reason="Token veya Chat ID eksik")
        return False

    if not settings.telegram_notify_drafts:
        log.debug("telegram_notification_disabled")
        return False

    text, reply_markup = format_draft_telegram_message(
        event=event,
        draft=draft,
        claims=claims,
        public_base_url=base_url,
    )

    endpoint = f"{TELEGRAM_API_BASE}{token}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": reply_markup,
        "disable_web_page_preview": True,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(endpoint, json=payload)
            if resp.status_code == 200:
                log.info(
                    "telegram_draft_notification_sent",
                    event_id=event.get("id"),
                    chat_id=target_chat,
                )
                return True
            log.warning(
                "telegram_notification_failed",
                status_code=resp.status_code,
                response=resp.text[:300],
            )
            return False
    except Exception as exc:  # noqa: BLE001
        log.warning("telegram_notification_exception", error=str(exc))
        return False


def send_telegram_test_message(
    *,
    bot_token: str | None = None,
    chat_id: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Telegram yapılandırmasını test etmek için örnek bildirim gönderir."""
    settings = get_settings()
    token = (settings.telegram_bot_token if bot_token is None else bot_token).strip()
    target_chat = (settings.telegram_chat_id if chat_id is None else chat_id).strip()

    if not token:
        return {"success": False, "error": "PD_TELEGRAM_BOT_TOKEN tanımlı değil."}
    if not target_chat:
        return {"success": False, "error": "PD_TELEGRAM_CHAT_ID tanımlı değil."}

    sample_event = {
        "id": 1,
        "title": "TCMB Politika Faizini %50 Seviyesinde Sabit Bıraktı",
        "salience_score": 88,
        "category": "Ekonomi",
        "status": "ready",
    }
    sample_draft = {
        "body": (
            "TCMB Para Politikası Kurulu, politika faizini beklentiler doğrultusunda "
            "%50 seviyesinde sabit tuttu. Kurul, enflasyonda belirgin ve kalıcı bir "
            "düşüş sağlanana kadar sıkı para politikası duruşunun sürdürüleceğini yineledi. "
            "#Ekonomi #TCMB"
        )
    }

    text, reply_markup = format_draft_telegram_message(
        event=sample_event,
        draft=sample_draft,
        public_base_url=settings.public_base_url,
    )

    # Test başlığı ekle
    test_header = (
        "🧪 <b>POLİTİKDESK TELEGRAM TEST PİNGİ</b>\n"
        "<i>Bu bir deneme bildirimidir.</i>\n\n"
    )
    text = test_header + text

    endpoint = f"{TELEGRAM_API_BASE}{token}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": reply_markup,
        "disable_web_page_preview": True,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(endpoint, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return {"success": True, "message_id": data.get("result", {}).get("message_id")}
            return {
                "success": False,
                "status_code": resp.status_code,
                "error": resp.text[:400],
            }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}
