"""Vaat Takibi (Promise Tracker) Ekranı (Spec v3.4 §7.3, §14.1).

Siyasi aktörlerin, liderlerin ve hükümet sözcülerinin verdikleri
vaatleri, kanunlaşma / gerçekleşme durumlarını ve resmi kaynak
teyitlerini tablo/kart görünümünde listeler.
"""

from __future__ import annotations

import urllib.parse

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from politikdesk.political_memory import service as mem_service
from politikdesk.political_memory.accountability import LEGAL_DISCLAIMER
from politikdesk.users import current_user_id, touch_last_seen
from politikdesk.web.ui import (
    ACTIVITY_JS,
    action_attrs,
    cell,
    esc,
    icon,
    kpi,
    notice,
    page,
    page_head,
    search_input,
)
from politikdesk.web.ui import format as fmt

router = APIRouter(tags=["web"])


def _outcome_badge(outcome: str) -> str:
    if outcome == "fulfils":
        return f'<span class="badge strong">{icon("check", 13)}Gerçekleşti (Kanunlaştı)</span>'
    if outcome in ("fails", "contradicts"):
        return f'<span class="badge contra">{icon("close", 13)}Çelişki / Reddedildi</span>'
    return f'<span class="badge partial">{icon("clock", 13)}Takipte / Süreç Devam Ediyor</span>'


_PROMISES_JS = """
(function(){
  var currentFilter = 'all';
  var currentQuery = '';

  function applyFilters() {
    var rows = document.querySelectorAll('#promises-table-body tr[data-outcome]');
    var visible = 0;
    var q = currentQuery.toLowerCase().trim();

    rows.forEach(function(r) {
      var outcome = r.dataset.outcome;
      var text = (r.dataset.search || '').toLowerCase();
      var matchesOutcome = (currentFilter === 'all') ||
        (currentFilter === 'fulfils' && outcome === 'fulfils') ||
        (currentFilter === 'contradicts' && (outcome === 'fails' || outcome === 'contradicts')) ||
        (currentFilter === 'pending' && outcome !== 'fulfils' && outcome !== 'fails' && outcome !== 'contradicts');
      var matchesText = !q || text.indexOf(q) !== -1;

      if (matchesOutcome && matchesText) {
        r.style.display = '';
        visible++;
      } else {
        r.style.display = 'none';
      }
    });

    var emptyEl = document.getElementById('promises-filter-empty');
    if (emptyEl) {
      emptyEl.style.display = (visible === 0 && rows.length > 0) ? '' : 'none';
    }
  }

  window.pdFilterPromises = function(filterKey, btn) {
    currentFilter = filterKey;
    document.querySelectorAll('#promises-tabs button').forEach(function(b) {
      b.removeAttribute('aria-current');
    });
    if (btn) btn.setAttribute('aria-current', 'true');
    applyFilters();
  };

  // Dagitici `input` olayinda (oge, olay) gecer; arama metni ogeden okunur.
  window.pdSearchPromises = function(el) {
    currentQuery = el.value;
    applyFilters();
  };

  window.pdAction('filter-promises', window.pdFilterPromises);
  window.pdAction('search-promises', window.pdSearchPromises);
})();
"""


def _empty_row(colspan: int) -> str:
    """Kayıt yokken başlık satırı tek başına kalmasın: neden boş ve ne zaman dolacağı yazılır."""
    return (
        f'<tr><td colspan="{colspan}" class="subtle" '
        'style="padding:var(--space-8) var(--space-4);text-align:center">'
        "Henüz takip edilen vaat yok. Siyasi hafıza adımı bir aktörün taahhüdünü "
        "kanun, karar ya da oylamayla eşleştirdiğinde burada listelenir."
        "</td></tr>"
    )


@router.get("/promises", response_class=HTMLResponse)
@router.get("/vaatler", response_class=HTMLResponse)
def promises_page() -> HTMLResponse:
    """Vaat Takibi ana ekranı."""
    try:
        user_id = current_user_id()
        touch_last_seen(user_id)
        promises = mem_service.get_promise_tracker()
    except Exception:  # noqa: BLE001
        promises = []


    total_count = len(promises)
    fulfilled_count = sum(1 for p in promises if p.get("outcome_relation") == "fulfils")
    contra_count = sum(
        1 for p in promises if p.get("outcome_relation") in ("fails", "contradicts")
    )
    pending_count = total_count - (fulfilled_count + contra_count)

    kpis_html = f"""
    <div class="kpis" style="margin-bottom:var(--space-6)">
      {kpi("Toplam Taahhüt", fmt.number(total_count), unit="vaat", icon_name="promise")}
      {kpi("Gerçekleşen", fmt.number(fulfilled_count), unit="kanun/karar", icon_name="check")}
      {kpi("Çelişen / Reddedilen", fmt.number(contra_count), unit="kayıt", icon_name="warning", higher_is_better=False)}
      {kpi("Takip Edilen", fmt.number(pending_count), unit="süreç", icon_name="clock")}
    </div>
    """

    disclaimer_html = notice(
        f"<p><b>Epistemik & Hukuki Çekince:</b> {esc(LEGAL_DISCLAIMER)}</p>"
    )



    rows_html = []
    for p in promises:
        outcome = p.get("outcome_relation") or "pending"
        badge = _outcome_badge(outcome)
        reported_date = esc(p.get("first_reported_at", "")[:10])
        speaker_raw = p.get("speaker") or "Belirtilmedi"
        speaker_esc = esc(speaker_raw)
        speaker_encoded = urllib.parse.quote(speaker_raw)
        title_esc = esc(p.get("event_title") or "Olay")
        claim_esc = esc(p.get("claim_text") or "")
        event_id = p.get("event_id")

        search_blob = f"{speaker_raw} {p.get('event_title', '')} {p.get('claim_text', '')}".replace(
            '"', "&quot;"
        )

        rows_html.append(
            f'<tr data-outcome="{esc(outcome)}" data-search="{esc(search_blob)}">'
            + cell(
                f'<div style="font-weight:var(--weight-medium)">{speaker_esc}</div>'
                f'<a href="/memory/{speaker_encoded}" class="subtle" style="font-size:var(--text-xs);display:inline-flex;align-items:center;gap:4px;margin-top:4px">'
                f'{icon("clock", 12)}Hafıza Profili &rarr;</a>',
                label="Aktör",
            )
            + cell(
                f'<a class="plain" href="/event/{event_id}" style="font-weight:var(--weight-medium)">{title_esc}</a>'
                f'<div class="claim-text" style="font-size:var(--text-xs);color:var(--color-fg-muted);margin-top:6px;font-style:italic">'
                f'“{claim_esc}”</div>',
                label="Vaat / Taahhüt",
            )
            + cell(badge, label="Durum")
            + cell(f'<span class="subtle mono">{reported_date}</span>', label="Tarih")
            + cell(
                f'<a class="btn sm ghost" href="/event/{event_id}">{icon("arrow-right", 14)}Olay</a>',
                label="İşlem",
            )
            + "</tr>"
        )

    filter_tabs_html = f"""
    <div class="row tight" style="align-items:center">
      <span class="subtle" style="font-size:var(--text-xs);display:flex;align-items:center;gap:4px">
        {icon("filter", 12)}Filtrele:
      </span>
      <div id="promises-tabs" class="segment">
        <button type="button" aria-current="true"{action_attrs("filter-promises", "all")}>Tümü ({total_count})</button>
        <button type="button"{action_attrs("filter-promises", "fulfils")}>Gerçekleşen ({fulfilled_count})</button>
        <button type="button"{action_attrs("filter-promises", "contradicts")}>Çelişen / Reddedilen ({contra_count})</button>
        <button type="button"{action_attrs("filter-promises", "pending")}>Takipte ({pending_count})</button>
      </div>
    </div>
    """

    headers = (
        ("Aktör", ""),
        ("Vaat / Taahhüt & Olay", ""),
        ("Doğrulanmış Durum", ""),
        ("İlk Kayıt", ""),
        ("İşlem", ""),
    )

    body = f"""
    {page_head(
        "Vaat Takip Masası",
        lede="Siyasi aktörlerin kamuoyuna verdikleri taahhütlerin, kanunlaşma süreçlerinin ve gerçekleşme kayıtlarının doğrulanmış kütüğü.",
        actions=search_input("promise-search", "Aktör veya vaat ara…", action="search-promises"),
    )}

    {kpis_html}
    <div style="margin-bottom:var(--space-4)">{disclaimer_html}</div>

    <div class="card flush">
      <div style="padding:var(--space-3) var(--space-4);border-bottom:1px solid var(--color-border);display:flex;align-items:center;gap:var(--space-3);flex-wrap:wrap">
        {filter_tabs_html}
      </div>
      <div class="table-wrap">
        <table class="table-cards">
          <thead>
            <tr>{''.join(f'<th class="{cls}">{esc(h)}</th>' for h, cls in headers)}</tr>
          </thead>
          <tbody id="promises-table-body">
            {''.join(rows_html) or _empty_row(len(headers))}
          </tbody>
        </table>
      </div>
      <div id="promises-filter-empty" style="display:none;padding:var(--space-8);text-align:center">
        <p class="subtle">Arama kriterlerine uygun vaat kaydı bulunamadı.</p>
      </div>
    </div>
    """

    combined_js = ACTIVITY_JS + "\n" + _PROMISES_JS
    return HTMLResponse(
        page(
            "Vaat Takibi",
            body,
            active="/promises",
            crumbs=(("Çalışma masası", None), ("Vaat Takibi", None)),
            extra_js=combined_js,
        )
    )
