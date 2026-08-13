"""Brifing gövdesi — HTML (e-posta) ve düz metin (F3-17).

E-posta HTML'i, uygulama içi sayfadan AYRI yazılır. Sebep teknik:
e-posta istemcileri harici CSS, `<style>` bloklarının çoğu, flexbox ve
grid desteklemez; gövde satır içi stille ve tablo düzeniyle kurulur.
Tek bir şablonu iki yere zorlamak, e-postada bozuk görünen bir sayfaya
yol açardı.

**Linkler mutlak olmalıdır** (F3-17 DoD: "e-posta HTML'de olay linkleri
çalışıyor"): göreli adres e-posta istemcisinde hiçbir şeye çözülmez.
Taban adres `PD_PUBLIC_BASE_URL` ile yapılandırılır.
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from politikdesk.config import get_settings

if TYPE_CHECKING:
    from politikdesk.briefing.generator import BriefingContent

_TEXT = "#1f2328"
_MUTED = "#656d76"
_BORDER = "#d0d7de"


def _base_url() -> str:
    return get_settings().public_base_url.rstrip("/")


def event_url(event_id: int) -> str:
    return f"{_base_url()}/event/{event_id}"


def open_pixel_url(token: str) -> str:
    return f"{_base_url()}/briefing/open/{token}.gif"


def _esc(text: object) -> str:
    return html.escape(str(text or ""))


def render_html(content: BriefingContent, *, open_token: str | None = None) -> str:
    """E-posta gövdesi. Satır içi stil, tablo düzeni, mutlak link."""
    from politikdesk.briefing.generator import EVENT_STATUS_TEXT, STATUS_BADGE

    rows: list[str] = []
    for index, event in enumerate(content.events, start=1):
        claim = ""
        if event.top_claim:
            badge = STATUS_BADGE.get(event.top_claim_status or "", "⚪")
            claim = (
                f'<div style="color:{_MUTED};font-size:14px;margin-top:4px">'
                f"{badge} {_esc(event.top_claim)}</div>"
            )
        diversity_color = _MUTED if event.independence_groups >= 2 else "#9a6700"
        rows.append(
            f"""
<tr><td style="padding:14px 0;border-bottom:1px solid {_BORDER}">
  <div style="font-size:12px;color:{_MUTED}">
    {index}. Salience {event.salience} ·
    {_esc(EVENT_STATUS_TEXT.get(event.status, event.status))} ·
    {event.article_count} makale · {event.independent_count} bağımsız teyit
  </div>
  <a href="{event_url(event.event_id)}"
     style="color:#0969da;font-size:17px;font-weight:600;text-decoration:none">
    {_esc(event.title)}</a>
  {claim}
  <div style="color:{diversity_color};font-size:12px;margin-top:4px">
    {_esc(event.diversity_note)}</div>
</td></tr>"""
        )

    upcoming = "".join(
        f'<li style="margin:4px 0">{_esc(u["expected_label"])} — {_esc(u["title"])}'
        + (f' <span style="color:{_MUTED}">({_esc(u["source_name"])})</span>'
           if u.get("source_name") else "")
        + "</li>"
        for u in content.upcoming
    )

    unverified = "".join(
        f'<li style="margin:6px 0">{_esc(u["badge"])} <b>{_esc(u["status_text"])}</b> — '
        f'{_esc(u["claim_text"])} '
        f'<a href="{event_url(u["event_id"])}" style="color:#0969da">→</a></li>'
        for u in content.unverified
    )

    sections = [
        f"""
<h2 style="font-size:15px;letter-spacing:.04em;color:{_MUTED};
           margin:28px 0 6px;text-transform:uppercase">Gündem</h2>
<table width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>"""
        if rows
        else f'<p style="color:{_MUTED}">Bu pencerede yeni olay yok.</p>'
    ]

    if upcoming:
        sections.append(
            f"""
<h2 style="font-size:15px;letter-spacing:.04em;color:{_MUTED};
           margin:28px 0 6px;text-transform:uppercase">Beklenen gelişmeler</h2>
<ul style="padding-left:18px;margin:0;font-size:15px">{upcoming}</ul>"""
        )

    if unverified:
        sections.append(
            f"""
<h2 style="font-size:15px;letter-spacing:.04em;color:{_MUTED};
           margin:28px 0 6px;text-transform:uppercase">Doğrulanmamış iddialar</h2>
<p style="color:{_MUTED};font-size:13px;margin:0 0 8px">
  Bunlar henüz teyit edilmedi. Doğrulanmış gibi paylaşılmamalıdır.</p>
<ul style="padding-left:18px;margin:0;font-size:15px">{unverified}</ul>"""
        )

    pixel = (
        f'<img src="{open_pixel_url(open_token)}" width="1" height="1" '
        f'alt="" style="display:block">'
        if open_token
        else ""
    )

    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(content.title)}</title></head>
<body style="margin:0;padding:24px;background:#f6f8fa;
             font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
             color:{_TEXT}">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0"
       style="background:#fff;border:1px solid {_BORDER};border-radius:8px;padding:28px">
<tr><td>
  <div style="font-size:12px;color:{_MUTED};letter-spacing:.08em">POLITIKDESK</div>
  <h1 style="font-size:22px;margin:6px 0 0">{_esc(content.title)}</h1>
  <p style="color:{_MUTED};font-size:13px;margin:6px 0 0">
    Salience sıralı. Skor <b>önem</b> gösterir, doğruluk değil.</p>
  {"".join(sections)}
  <p style="margin-top:28px;font-size:13px;color:{_MUTED};
            border-top:1px solid {_BORDER};padding-top:14px">
    <a href="{_base_url()}/feed" style="color:#0969da">Feed'i aç</a> ·
    AI senin yerine konuşmaz; gündemi senin adına takip eder.</p>
  {pixel}
</td></tr></table>
</td></tr></table>
</body></html>"""


def render_text(content: BriefingContent) -> str:
    """Düz metin sürümü — HTML kapalı istemciler ve uygulama içi önizleme."""
    from politikdesk.briefing.generator import EVENT_STATUS_TEXT, STATUS_BADGE

    lines = [content.title, "=" * len(content.title), ""]

    if content.events:
        lines.append("GÜNDEM")
        for index, event in enumerate(content.events, start=1):
            lines.append(
                f"{index}. [{event.salience}] {event.title} "
                f"({EVENT_STATUS_TEXT.get(event.status, event.status)}, "
                f"{event.article_count} makale, "
                f"{event.independent_count} bağımsız teyit)"
            )
            if event.top_claim:
                badge = STATUS_BADGE.get(event.top_claim_status or "", "⚪")
                lines.append(f"   {badge} {event.top_claim}")
            lines.append(f"   {event.diversity_note}")
            lines.append(f"   {event_url(event.event_id)}")
        lines.append("")
    else:
        lines += ["Bu pencerede yeni olay yok.", ""]

    if content.upcoming:
        lines.append("BEKLENEN GELİŞMELER")
        for item in content.upcoming:
            source = f" ({item['source_name']})" if item.get("source_name") else ""
            lines.append(f"  - {item['expected_label']} — {item['title']}{source}")
        lines.append("")

    if content.unverified:
        lines.append("DOĞRULANMAMIŞ İDDİALAR")
        lines.append("  Bunlar henüz teyit edilmedi; doğrulanmış gibi paylaşılmamalıdır.")
        for item in content.unverified:
            lines.append(
                f"  {item['badge']} [{item['status_text']}] {item['claim_text']}"
            )
        lines.append("")

    lines.append(f"Feed: {_base_url()}/feed")
    return "\n".join(lines)
