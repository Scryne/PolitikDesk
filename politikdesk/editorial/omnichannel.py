"""Omnichannel Editoryal Yayın Formatlayıcı ve Dejavu Koruması (Spec §12.4, B-29).

Üretilen editoryal analizleri, teyitli olayları ve taslakları tek tıkla 4 temel
platform formatına dönüştürür ve editoryal tekrar/dejavu denetimi yapar:
  1. X (Twitter) Thread Dizisi
  2. LinkedIn Analitik Gönderi
  3. Telegram / WhatsApp Bülten Notu
  4. Newsletter / Web Yayını Markdown/HTML
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from politikdesk.db import connection
from politikdesk.editorial.social_publisher import evaluate_social_safety_gate
from politikdesk.observability import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class RepetitionAlert:
    """Tekrarlayan içerik uyarısı."""

    is_duplicate_risk: bool
    similarity_score: float
    matched_draft_id: int | None = None
    matched_title: str | None = None
    days_ago: int | None = None
    warning_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OmnichannelPackage:
    """4 platform için hazırlanmış çoklu yayın paketi."""

    event_id: int
    draft_id: int | None
    title: str
    lead: str
    x_thread: list[str]
    linkedin_post: str
    telegram_note: str
    newsletter_markdown: str
    safety_gate: dict[str, Any]
    repetition_alert: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_anti_repetition(
    title: str,
    body: str,
    *,
    event_id: int | None = None,
    days_window: int = 30,
) -> RepetitionAlert:
    """Son 30 gündeki taslaklarla benzerlik karşılaştırması yapar."""
    sql = """
        SELECT d.id, d.title, d.created_at,
               EXTRACT(DAY FROM (now() - d.created_at))::int AS days_ago
        FROM drafts d
        WHERE d.created_at >= now() - make_interval(days => %s)
          AND (%s IS NULL OR d.event_id != %s)
        ORDER BY d.created_at DESC
        LIMIT 50
    """
    title_words = set(title.casefold().split())

    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (days_window, event_id, event_id))
            rows = cur.fetchall()
    except Exception as exc:
        log.warning("anti_repetition_db_error", error=str(exc))
        return RepetitionAlert(
            is_duplicate_risk=False,
            similarity_score=0.0,
            warning_message="Tekrar kontrolü yapılamadı (veritabanı erişilemez).",
        )

    for r in rows:
        past_title = r.get("title") or ""
        past_words = set(past_title.casefold().split())
        if not past_words or not title_words:
            continue
        intersection = title_words.intersection(past_words)
        jaccard = len(intersection) / len(title_words.union(past_words))

        if jaccard >= 0.35:
            days = r.get("days_ago") or 0
            return RepetitionAlert(
                is_duplicate_risk=True,
                similarity_score=round(jaccard, 2),
                matched_draft_id=r["id"],
                matched_title=past_title,
                days_ago=days,
                warning_message=(
                    f"Bu konu ve benzer başlık {days} gün önce '{past_title}' "
                    f"taslağında işlenmiş görünüyor (Benzerlik: %{int(jaccard * 100)})."
                ),
            )

    return RepetitionAlert(
        is_duplicate_risk=False,
        similarity_score=0.0,
        warning_message="Taze içerik; son 30 günde benzer taslak tespit edilmedi.",
    )


def format_x_thread(
    title: str,
    lead: str,
    claims: list[dict[str, Any]],
    event_id: int,
    *,
    base_url: str = "https://politikdesk.com",
    max_tweet_len: int = 280,
) -> list[str]:
    """X (Twitter) için numaralandırılmış, kancalı thread dizisi."""
    tweets: list[str] = []
    event_url = f"{base_url}/event/{event_id}"

    # Tweet 1: Hook + Lede + Kanıt Kütüğü Linki
    t1 = f"📌 {title}\n\n{lead[:140]}...\n\n🔗 Kanıt Kütüğü: {event_url}"
    tweets.append(t1[:max_tweet_len])

    # Atomik İddialar
    for idx, c in enumerate(claims, 1):
        status = c.get("evidence_status", "single_source")
        badge = (
            "🟢 [Teyitli]"
            if status == "strongly_corroborated"
            else ("🟡 [Kısmi Teyit]" if status == "partially_corroborated" else "⚪ [Beyan]")
        )
        claim_text = c.get("claim_text", "").strip()
        speaker = c.get("speaker", "").strip()
        speaker_str = f"{speaker}: " if speaker else ""
        src = c.get("source", "Resmî Kaynak")

        tweet_body = f"{idx}/{len(claims)} {badge} {speaker_str}“{claim_text}”\n\n📌 Kaynak: {src}"
        tweets.append(tweet_body[:max_tweet_len])

    return tweets


def format_linkedin_post(
    title: str,
    lead: str,
    claims: list[dict[str, Any]],
    event_id: int,
    *,
    base_url: str = "https://politikdesk.com",
) -> str:
    """LinkedIn için yönetici seviyesinde analitik makale formatı."""
    event_url = f"{base_url}/event/{event_id}"
    lines = [
        f"🔍 ANALİZ & POLİTİKA İSTİHBARATI: {title}",
        "",
        "Özet Değerlendirme:",
        lead,
        "",
        "📊 Öne Çıkan Bulgular ve Teyit Durumu:",
    ]

    for _idx, c in enumerate(claims, 1):
        status = c.get("evidence_status", "single_source")
        if status == "strongly_corroborated":
            status_label = "✅ Doğrulandı"
        elif status == "partially_corroborated":
            status_label = "⚠️ Kısmen Doğrulandı"
        else:
            status_label = "ℹ️ Beyan / İddia"

        claim_text = c.get("claim_text", "").strip()
        speaker = c.get("speaker", "").strip()
        speaker_str = f" ({speaker})" if speaker else ""
        lines.append(f"• [{status_label}]{speaker_str}: {claim_text}")

    lines.extend([
        "",
        f"📌 Doğruluk ve Kanıt Matrisi Detayları: {event_url}",
        "",
        "#PolitikDesk #SiyasiHafıza #Ekonomi #Teyit #VeriGazeteciligi #PolitikaAnalizi",
    ])
    return "\n".join(lines)


def format_telegram_note(
    title: str,
    lead: str,
    claims: list[dict[str, Any]],
    event_id: int,
    *,
    base_url: str = "https://politikdesk.com",
) -> str:
    """Telegram / WhatsApp için hızlı okunabilir bülten bilgi notu."""
    event_url = f"{base_url}/event/{event_id}"
    lines = [
        f"⚡ *{title}*",
        "",
        f"_{lead}_",
        "",
        "*Önemli Maddeler:*",
    ]

    for _idx, c in enumerate(claims, 1):
        status = c.get("evidence_status", "single_source")
        icon = (
            "🟢"
            if status == "strongly_corroborated"
            else ("🟡" if status == "partially_corroborated" else "⚪")
        )
        claim_text = c.get("claim_text", "").strip()
        lines.append(f"{icon} {claim_text}")

    lines.extend([
        "",
        f"👉 [Kanıt Kütüğü ve Metrikler]({event_url})",
    ])
    return "\n".join(lines)


def format_newsletter_markdown(
    title: str,
    lead: str,
    claims: list[dict[str, Any]],
    event_id: int,
    *,
    base_url: str = "https://politikdesk.com",
) -> str:
    """Newsletter / E-posta bülteni için zengin Markdown formatı."""
    event_url = f"{base_url}/event/{event_id}"
    lines = [
        f"# {title}",
        "",
        f"> **Giriş:** {lead}",
        "",
        "## Doğrulanan Olay ve Kanıt Matrisi",
        "",
        "| # | İddia / Beyan | Konuşmacı | Kanıt Durumu |",
        "|---|---|---|---|",
    ]

    for idx, c in enumerate(claims, 1):
        status = c.get("evidence_status", "single_source")
        badge = (
            "🟢 Teyitli"
            if status == "strongly_corroborated"
            else ("🟡 Kısmi Teyit" if status == "partially_corroborated" else "⚪ Beyan")
        )
        claim_text = c.get("claim_text", "").strip().replace("|", "/")
        speaker = (c.get("speaker") or "-").replace("|", "/")
        lines.append(f"| {idx} | {claim_text} | {speaker} | {badge} |")

    lines.extend([
        "",
        f"Bu analiz [PolitikDesk Editoryal Masası]({event_url}) "
        "tarafından nesnel ve teyitli kaynaklardan derlenmiştir.",
    ])
    return "\n".join(lines)


def build_omnichannel_package_from_event(
    event_id: int,
    *,
    draft_id: int | None = None,
    custom_title: str | None = None,
    custom_body: str | None = None,
) -> OmnichannelPackage:
    """Bir olay veya taslak için 4 platformluk yayın paketini üretir."""
    # Olay ve iddiaları veritabanından çek
    sql = """
        SELECT e.id, e.title, e.summary,
               COALESCE(json_agg(json_build_object(
                   'claim_text', c.claim_text,
                   'speaker', c.speaker,
                   'claim_type', c.claim_type,
                   'evidence_status', c.evidence_status
               )) FILTER (WHERE c.id IS NOT NULL), '[]'::json) AS claims_json
        FROM events e
        LEFT JOIN claims c ON c.event_id = e.id
        WHERE e.id = %s
        GROUP BY e.id, e.title, e.summary
    """
    row = None
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (event_id,))
            row = cur.fetchone()
    except Exception as exc:
        log.warning("omnichannel_fetch_event_failed", event_id=event_id, error=str(exc))

    if not row:
        title = str(custom_title or f"Politik Gelişme #{event_id}")
        lead = str(custom_body or "Olay detayları yükleniyor...")
        claims_list: list[dict[str, Any]] = []
    else:
        title = str(custom_title or row.get("title") or f"Politik Gelişme #{event_id}")
        lead = str(custom_body or row.get("summary") or row.get("title") or "")
        claims_raw = row.get("claims_json")
        claims_list = claims_raw if isinstance(claims_raw, list) else []

    # Formatlamalar
    x_thread = format_x_thread(title, lead, claims_list, event_id)
    linkedin_post = format_linkedin_post(title, lead, claims_list, event_id)
    telegram_note = format_telegram_note(title, lead, claims_list, event_id)
    newsletter_md = format_newsletter_markdown(title, lead, claims_list, event_id)

    # Güvenlik kapısı denetimi
    combined_text = f"{title} {lead} " + " ".join(x_thread)
    gate = evaluate_social_safety_gate(combined_text)

    # Dejavu / Tekrar koruması
    rep_alert = check_anti_repetition(title, lead, event_id=event_id)

    return OmnichannelPackage(
        event_id=event_id,
        draft_id=draft_id,
        title=title,
        lead=lead,
        x_thread=x_thread,
        linkedin_post=linkedin_post,
        telegram_note=telegram_note,
        newsletter_markdown=newsletter_md,
        safety_gate=asdict(gate),
        repetition_alert=rep_alert.to_dict(),
    )
