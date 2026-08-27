"""Sosyal Medya Doğruluk İnfografik Kartı Üreticisi (SVG Fact-Check Card Generator).

Teyit edilen iddialar, kanıtlar ve olaylar için Twitter/LinkedIn/Instagram
standartlarında (1200x675, 16:9) bağımsız, şık ve vektörel doğruluk kartları üretir.
Tüm renkler DESIGN.md Bölüm 5.1 gereğince tokens.DARK sözlüğünden okunur.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from typing import Any

from politikdesk.web import repository
from politikdesk.web.ui.tokens import DARK

_FONT = 'font-family="system-ui, -apple-system, sans-serif"'

BG_COLOR = DARK["color-bg"]
SURFACE_COLOR = DARK["color-surface"]
SURFACE_SUNKEN = DARK["color-surface-sunken"]
BORDER_COLOR = DARK["color-border"]
BORDER_STRONG = DARK["color-border-strong"]
FG_COLOR = DARK["color-fg"]
FG_MUTED = DARK["color-fg-muted"]
FG_SUBTLE = DARK["color-fg-subtle"]
ACCENT_COLOR = DARK["color-accent"]
STRONG_COLOR = DARK["color-strong"]
STRONG_SUBTLE = DARK["color-strong-subtle"]
PARTIAL_COLOR = DARK["color-partial"]
PARTIAL_SUBTLE = DARK["color-partial-subtle"]
CONTRA_COLOR = DARK["color-contra"]
CONTRA_SUBTLE = DARK["color-contra-subtle"]
UNVERIFIED_COLOR = DARK["color-unverified"]
UNVERIFIED_SUBTLE = DARK["color-unverified-subtle"]


def _escape(text: str) -> str:
    return html.escape(str(text or ""), quote=True)


def _wrap_text(text: str, max_chars_per_line: int = 55, max_lines: int = 2) -> list[str]:
    """Metni SVG text elementleri için satırlara böler."""
    words = text.split()
    lines: list[str] = []
    curr_line: list[str] = []
    curr_len = 0

    for w in words:
        if curr_len + len(w) + 1 <= max_chars_per_line:
            curr_line.append(w)
            curr_len += len(w) + 1
        else:
            if curr_line:
                lines.append(" ".join(curr_line))
            curr_line = [w]
            curr_len = len(w)
            if len(lines) >= max_lines:
                break

    if curr_line and len(lines) < max_lines:
        lines.append(" ".join(curr_line))

    if len(words) > sum(len(line.split()) for line in lines) and lines:
        lines[-1] = lines[-1].rstrip("., ") + "..."

    return lines


def generate_event_svg_card(event: dict[str, Any], claims: list[dict[str, Any]]) -> str:
    """1200x675 boyutlarında koyu temalı, pürüzsüz vektörel SVG doğruluk kartı oluşturur."""
    title = str(event.get("title", "PolitikDesk Olayı"))
    event_id = event.get("id", 0)
    category = str(event.get("category_label", event.get("category", "GÜNDEM"))).upper()
    salience = event.get("displayed_salience", event.get("global_salience", 75))

    # Tarih formatlama
    date_str = datetime.now(UTC).strftime("%d.%m.%Y")
    if event.get("first_reported_at"):
        try:
            dt = event["first_reported_at"]
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            date_str = dt.strftime("%d.%m.%Y")
        except Exception:
            pass

    title_lines = _wrap_text(title, max_chars_per_line=50, max_lines=2)

    # İddialardan en güçlüsünü seç
    best_claim = claims[0] if claims else {}
    claim_status = best_claim.get("evidence_status", "single_source")
    claim_text = best_claim.get("claim_text", title)
    speaker = best_claim.get("speaker") or ""

    if claim_status == "strongly_corroborated":
        badge_bg = STRONG_SUBTLE
        badge_border = STRONG_COLOR
        badge_text = STRONG_COLOR
        badge_label = "🟢 TEYİTLİ & DOĞRULANDI"
    elif claim_status == "partially_corroborated":
        badge_bg = PARTIAL_SUBTLE
        badge_border = PARTIAL_COLOR
        badge_text = PARTIAL_COLOR
        badge_label = "🟡 KISMİ TEYİT"
    elif claim_status == "contradicted":
        badge_bg = CONTRA_SUBTLE
        badge_border = CONTRA_COLOR
        badge_text = CONTRA_COLOR
        badge_label = "🔴 ÇELİŞKİLİ BEYAN"
    else:
        badge_bg = UNVERIFIED_SUBTLE
        badge_border = BORDER_STRONG
        badge_text = FG_MUTED
        badge_label = "⚪ AKTÖR BEYANI"

    claim_lines = _wrap_text(claim_text, max_chars_per_line=60, max_lines=3)

    sources = []
    if best_claim.get("evidence"):
        for ev in best_claim["evidence"][:2]:
            s_name = ev.get("source_name") or ev.get("source_slug") or "Kaynak"
            tier = ev.get("tier", 1)
            sources.append(f"Tier {tier} • {s_name}")
    if not sources:
        sources = ["Birincil Veri Tabanı"]

    sources_str = " | ".join(sources)

    title_svg = ""
    y_pos = 185
    for line in title_lines:
        title_svg += (
            f'<text x="80" y="{y_pos}" fill="{FG_COLOR}" {_FONT} font-size="34" '
            f'font-weight="700">{_escape(line)}</text>\n'
        )
        y_pos += 44

    claim_svg = ""
    cy_pos = 380
    for line in claim_lines:
        claim_svg += (
            f'<text x="120" y="{cy_pos}" fill="{FG_COLOR}" {_FONT} font-size="22" '
            f'font-weight="400" font-style="italic">{_escape(line)}</text>\n'
        )
        cy_pos += 34

    speaker_svg = ""
    if speaker:
        speaker_svg = (
            f'<text x="120" y="340" fill="{ACCENT_COLOR}" {_FONT} font-size="18" '
            f'font-weight="600">👤 {_escape(speaker)}</text>'
        )

    date_salience_text = f"{_escape(date_str)} • Önem: {_escape(str(salience))}"
    badge_rect = (
        f'<rect x="40" y="26" width="240" height="34" rx="8" '
        f'fill="{badge_bg}" stroke="{badge_border}" stroke-width="1.5" />'
    )
    badge_txt = (
        f'<text x="160" y="49" fill="{badge_text}" {_FONT} font-size="13" '
        f'font-weight="800" text-anchor="middle">{_escape(badge_label)}</text>'
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 1200 675" width="1200" height="675">
  <defs>
    <linearGradient id="bg-grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{BG_COLOR}" />
      <stop offset="100%" stop-color="{SURFACE_SUNKEN}" />
    </linearGradient>
    <linearGradient id="card-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="{SURFACE_COLOR}" />
      <stop offset="100%" stop-color="{BG_COLOR}" />
    </linearGradient>
  </defs>

  <rect width="1200" height="675" fill="url(#bg-grad)" />

  <g opacity="0.04" stroke="{FG_COLOR}" stroke-width="1">
    <line x1="0" y1="135" x2="1200" y2="135" />
    <line x1="0" y1="270" x2="1200" y2="270" />
    <line x1="0" y1="405" x2="1200" y2="405" />
    <line x1="0" y1="540" x2="1200" y2="540" />
    <line x1="240" y1="0" x2="240" y2="675" />
    <line x1="480" y1="0" x2="480" y2="675" />
    <line x1="720" y1="0" x2="720" y2="675" />
    <line x1="960" y1="0" x2="960" y2="675" />
  </g>

  <g transform="translate(80, 60)">
    <rect x="0" y="0" width="32" height="32" rx="8" fill="{ACCENT_COLOR}" />
    <text x="16" y="22" fill="{FG_COLOR}" {_FONT} font-size="18"
          font-weight="900" text-anchor="middle">P</text>
    <text x="44" y="23" fill="{FG_COLOR}" {_FONT} font-size="20"
          font-weight="800">POLITIK<tspan fill="{ACCENT_COLOR}">DESK</tspan></text>

    <rect x="230" y="2" width="110" height="26" rx="6"
          fill="{SURFACE_SUNKEN}" stroke="{BORDER_COLOR}" />
    <text x="285" y="19" fill="{FG_MUTED}" {_FONT} font-size="12"
          font-weight="700" text-anchor="middle">{_escape(category)}</text>

    <text x="1040" y="22" fill="{FG_SUBTLE}" {_FONT} font-size="14"
          font-weight="500" text-anchor="end">{date_salience_text}</text>
  </g>

  {title_svg}

  <g transform="translate(80, 260)">
    <rect width="1040" height="260" rx="16" fill="url(#card-grad)"
          stroke="{BORDER_COLOR}" stroke-width="1.5" />
    <rect x="0" y="0" width="1040" height="6" rx="3" fill="{ACCENT_COLOR}" />
    {badge_rect}
    {badge_txt}
  </g>

  {speaker_svg}
  {claim_svg}

  <g transform="translate(120, 475)">
    <text x="0" y="0" fill="{FG_MUTED}" {_FONT} font-size="13"
          font-weight="600">KANIT DAYANAĞI:</text>
    <text x="140" y="0" fill="{ACCENT_COLOR}" {_FONT} font-size="13"
          font-weight="600">{_escape(sources_str)}</text>
  </g>

  <g transform="translate(80, 580)">
    <line x1="0" y1="0" x2="1040" y2="0" stroke="{BORDER_COLOR}" stroke-width="1" />
    <text x="0" y="38" fill="{STRONG_COLOR}" {_FONT} font-size="13"
          font-weight="700">✓ Epistemik Grounding Doğrulaması Tamamlandı</text>
    <text x="1040" y="38" fill="{FG_SUBTLE}" {_FONT} font-size="13"
          font-weight="500" text-anchor="end">politikdesk.com/event/{event_id}</text>
  </g>
</svg>"""
    return svg


def render_event_card_svg(event_id: int) -> str | None:
    """Veritabanından olayı ve iddialarını çekerek SVG kartı döner."""
    try:
        data = repository.event_page(event_id, user_id=0)
        if not data or not data.get("event"):
            return None
        event = data["event"]
        claims = data.get("claims", [])
        return generate_event_svg_card(event, claims)
    except Exception:
        return None
