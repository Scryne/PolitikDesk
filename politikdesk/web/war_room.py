"""PolitikDesk Haber Masası / Kumanda Odası (War Room Live Monitor).

Büyük ekranlar, editoryal ekipler ve anlık gündem takibi için tasarlanmış
canlı, reaktif ve çok sütunlu editoryal kumanda merkezi.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from politikdesk.observability import get_logger
from politikdesk.users import current_user_id
from politikdesk.web import repository
from politikdesk.web.ui.components import (
    card,
    esc,
    event_badge,
    kpi,
    page_head,
    status_badge,
)
from politikdesk.web.ui.icons import icon
from politikdesk.web.ui.shell import ACTIVITY_JS, page

log = get_logger(__name__)
router = APIRouter(tags=["war_room"])


def _war_room_js() -> str:
    return """
(function(){
  var sseSource = null;
  function connectSSE(){
    if (window.EventSource) {
      try {
        sseSource = new EventSource('/api/events/stream');
        sseSource.addEventListener('event_updated', function(e){
          var data = JSON.parse(e.data || '{}');
          if (data && data.title) {
            window.pdToast('Yeni Gelişme: ' + data.title);
            var dot = document.getElementById('wr-live-dot');
            if (dot) {
              dot.style.background = 'var(--color-accent)';
              setTimeout(function(){ dot.style.background = 'var(--color-strong)'; }, 2000);
            }
          }
        });
      } catch (err) {}
    }
  }
  connectSSE();
})();
"""


@router.get("/war-room", response_class=HTMLResponse)
@router.get("/radar", response_class=HTMLResponse, include_in_schema=False)
def war_room_page() -> str:
    """Canlı Editoryal Kumanda Odası Görünümü."""
    user_id = current_user_id()
    try:
        events = repository.feed(user_id=user_id, limit=30)
    except Exception as exc:  # noqa: BLE001
        log.warning("war_room_feed_failed", error=str(exc))
        events = []

    # İstatistikler & Öne Çıkanlar
    strong_count = sum(1 for e in events if e.get("top_claim_status") == "strongly_corroborated")
    breaking_events = [e for e in events if (e.get("salience_score") or 0) >= 55]

    # Breaking News Bar
    breaking_cards = []
    for ev in breaking_events[:3]:
        sal = ev.get("salience_score", 0)
        breaking_cards.append(
            f'<div class="card" style="border-left:4px solid var(--color-accent);'
            f'background:var(--color-surface-sunken);margin-bottom:var(--space-2);padding:var(--space-3);">'
            f'<div class="row" style="justify-content:space-between;margin-bottom:4px;">'
            f'<span style="font-size:var(--text-xs);font-weight:var(--weight-bold);color:var(--color-accent);'
            f'display:flex;align-items:center;gap:4px;">{icon("zap", 12)} KRİTİK GÜNDEM ({sal}/90)</span>'
            f'<span style="font-size:var(--text-xs);color:var(--color-fg-subtle);">'
            f'{ev.get("article_count", 0)} Bağımsız Kaynak</span>'
            f'</div>'
            f'<a href="/event/{ev["id"]}" style="font-weight:var(--weight-semibold);font-size:var(--text-sm);'
            f'color:var(--color-fg);text-decoration:none;line-height:1.4;display:block;">'
            f'{esc(ev["title"])}</a>'
            f'</div>'
        )
    breaking_section = "".join(breaking_cards) if breaking_cards else (
        '<div style="color:var(--color-fg-subtle);font-size:var(--text-sm);padding:var(--space-2);">'
        'Şu anda 55+ skora sahip kritik gündem kırılması bulunmuyor.</div>'
    )

    # Event Ticker Table / Stream
    event_rows = []
    for ev in events:
        sal = ev.get("salience_score", 0)
        top_status = ev.get("top_claim_status", "unverified")
        src_count = ev.get("article_count", 0)
        clm_count = ev.get("claim_count", 0)

        badge = status_badge(top_status)
        ev_type_badge = event_badge(ev.get("status", "developing"))

        event_rows.append(
            f'<tr style="border-bottom:1px solid var(--color-border);">'
            f'<td style="padding:var(--space-3) var(--space-2);width:50px;text-align:center;">'
            f'<span style="font-family:var(--font-mono);font-size:var(--text-xs);font-weight:var(--weight-bold);'
            f'color:var(--color-accent);">{sal}</span></td>'
            f'<td style="padding:var(--space-3) var(--space-2);">'
            f'<a href="/event/{ev["id"]}" style="font-weight:var(--weight-semibold);color:var(--color-fg);'
            f'text-decoration:none;font-size:var(--text-sm);">{esc(ev["title"])}</a>'
            f'<div class="row" style="gap:var(--space-2);margin-top:4px;font-size:var(--text-xs);'
            f'color:var(--color-fg-muted);">'
            f'<span>{src_count} Kaynak</span> · <span>{clm_count} İddia</span>'
            f'</div></td>'
            f'<td style="padding:var(--space-3) var(--space-2);white-space:nowrap;">{badge}</td>'
            f'<td style="padding:var(--space-3) var(--space-2);white-space:nowrap;">{ev_type_badge}</td>'
            f'<td style="padding:var(--space-3) var(--space-2);text-align:right;white-space:nowrap;">'
            f'<a class="btn sm ghost" href="/event/{ev["id"]}" title="İncele">{icon("arrow-right", 12)}</a>'
            f'</td></tr>'
        )

    table_html = (
        '<table style="width:100%;border-collapse:collapse;font-size:var(--text-sm);">'
        '<thead><tr style="border-bottom:2px solid var(--color-border);text-align:left;'
        'color:var(--color-fg-subtle);font-size:var(--text-xs);">'
        '<th style="padding:var(--space-2);text-align:center;">SKOR</th>'
        '<th style="padding:var(--space-2);">GÜNDEM BAŞLIĞI</th>'
        '<th style="padding:var(--space-2);">KANIT DURUMU</th>'
        '<th style="padding:var(--space-2);">AŞAMA</th>'
        '<th style="padding:var(--space-2);text-align:right;">EYLEM</th>'
        '</tr></thead><tbody>'
        + "".join(event_rows)
        + '</tbody></table>'
    )

    kpis = (
        f'<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr));'
        f'gap:var(--space-4);margin-bottom:var(--space-6);">'
        f'{kpi("CANLI AKIŞ", f"{len(events)} Olay", delta_note="Son 24 saatte toplanan kümeler", icon_name="clock")}'
        f'{kpi("GÜÇLÜ TEYİTLİ", f"{strong_count}", delta_note="T1 ve çoklu bağımsız kaynak teyidi", icon_name="check")}'
        f'{kpi("KRİTİK GÜNDEM", f"{len(breaking_events)}", delta_note="Gündem skoru 55 ve üzeri olaylar", icon_name="zap")}'
        f'{kpi("HABER BORU HATTI", "Aktif", delta_note="5 dk periyodik otomatik tarama", icon_name="shield")}'
        f'</div>'
    )

    body = f"""
{
        page_head(
            "Haber Masası & Canlı Kumanda Odası",
            lede="Tüm canlı veri kaynaklarının, kanıt zincirlerinin ve anlık gündem kırılmalarının eşzamanlı izleme radarı.",
            badges='<span class="badge sm" style="background:var(--color-surface-sunken);color:var(--color-strong);display:inline-flex;align-items:center;gap:6px;"><span id="wr-live-dot" class="pulse-dot"></span> CANLI YAYIN</span>',
            actions='<a class="btn sm" href="/feed" title="Klasik Çalışma Masası">' + icon("feed", 13) + '<span>Gündem Masası</span></a>',
        )
    }

{kpis}

<div class="split">
  <div class="stack" style="flex:2">
    {card(table_html, title="Anlık Gündem & Olay Akışı")}
  </div>
  <div class="stack" style="flex:1;position:sticky;top:calc(var(--topbar-h) + 24px)">
    {card(breaking_section, title="Kritik Kırılmalar")}
    {
        card(
            '<div style="font-size:var(--text-xs);color:var(--color-fg-muted);line-height:1.6;">'
            '<p style="margin:0 0 var(--space-2)"><b>Kısayollar:</b></p>'
            '<p style="margin:0 0 4px"><kbd class="shortcut-key">J</kbd> / <kbd class="shortcut-key">K</kbd> : Olaylar arasında gezin</p>'
            '<p style="margin:0 0 4px"><kbd class="shortcut-key">X</kbd> : Hızlı X taslağı aç</p>'
            '<p style="margin:0 0 4px"><kbd class="shortcut-key">Ctrl+K</kbd> : Komuta paleti / Hızlı arama</p>'
            '</div>',
            title="Kumanda Kılavuzu",
        )
    }
  </div>
</div>
"""

    return page(
        "Haber Masası / Kumanda Odası",
        body,
        active="/war-room",
        crumbs=(("Kumanda Odası", "/war-room"),),
        extra_js=ACTIVITY_JS + _war_room_js(),
    )
