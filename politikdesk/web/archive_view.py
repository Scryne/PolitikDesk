"""Editoryal Yayın ve Kanıt Arşivi Ekranı (Spec v3.4 §14.4).

PolitikDesk üzerinden üretilen, düzenlenen ve yayınlanan
tüm içeriklerin dayandığı kanıt bağlarını (`cited_claim_ids`),
model sürümlerini ve denetim kütüğünü gösterir.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from politikdesk.editorial.archive import list_archived_publications
from politikdesk.users import current_user_id, touch_last_seen
from politikdesk.web.ui import (
    ACTIVITY_JS,
    action_attrs,
    esc,
    icon,
    kpi,
    page,
    page_head,
    ruled,
    search_input,
)
from politikdesk.web.ui import format as fmt

router = APIRouter(tags=["web"])

_ARCHIVE_JS = """
(function(){
  var currentAngle = 'all';
  var currentQuery = '';

  function applyFilters() {
    var cards = document.querySelectorAll('#archive-list [data-angle]');
    var visible = 0;
    var q = currentQuery.toLowerCase().trim();

    cards.forEach(function(c) {
      var angle = c.dataset.angle;
      var text = (c.dataset.search || '').toLowerCase();
      var matchesAngle = (currentAngle === 'all') || (currentAngle === angle);
      var matchesText = !q || text.indexOf(q) !== -1;

      if (matchesAngle && matchesText) {
        c.style.display = '';
        visible++;
      } else {
        c.style.display = 'none';
      }
    });

    var emptyEl = document.getElementById('archive-filter-empty');
    if (emptyEl) {
      emptyEl.style.display = (visible === 0 && cards.length > 0) ? '' : 'none';
    }
  }

  window.pdFilterArchive = function(angleKey, btn) {
    currentAngle = angleKey;
    document.querySelectorAll('#archive-tabs button').forEach(function(b) {
      b.removeAttribute('aria-current');
    });
    if (btn) btn.setAttribute('aria-current', 'true');
    applyFilters();
  };

  // Dağıtıcı `input` olayında (öğe, olay) geçer; arama metni öğeden okunur.
  window.pdSearchArchive = function(el) {
    currentQuery = el.value;
    applyFilters();
  };

  window.pdAction('filter-archive', window.pdFilterArchive);
  window.pdAction('search-archive', window.pdSearchArchive);
})();
"""


@router.get("/archive", response_class=HTMLResponse)
@router.get("/arsiv", response_class=HTMLResponse)
def archive_page() -> HTMLResponse:
    """Yayın Arşivi ana ekranı."""
    try:
        user_id = current_user_id()
        touch_last_seen(user_id)
        records = list_archived_publications(limit=100)
    except Exception:  # noqa: BLE001
        records = []


    total_records = len(records)
    grounded_count = sum(1 for r in records if r.get("is_grounded"))
    grounded_rate = round(grounded_count / total_records * 100) if total_records > 0 else 100
    avg_claims = (
        round(sum(len(r.get("cited_claim_ids") or []) for r in records) / total_records, 1)
        if total_records > 0
        else 0
    )

    kpis_html = f"""
    <div class="kpis" style="margin-bottom:var(--space-6)">
      {kpi("Yayınlanan İçerik", fmt.number(total_records), unit="metin", icon_name="archive")}
      {kpi("Doğrulanmış Grounding", f"%{grounded_rate}", unit="oran", icon_name="check")}
      {kpi("Ortalama Dayanak", str(avg_claims), unit="iddia / metin", icon_name="shield")}
      {kpi("Editoryal Süreç", fmt.number(total_records), unit="kayıt", icon_name="edit")}
    </div>
    """



    cards_html = []
    angles_present: set[str] = set()

    for r in records:
        angle_raw = (r.get("angle") or "inform").lower()
        angles_present.add(angle_raw)
        is_grounded = bool(r.get("is_grounded"))
        tone = "strong" if is_grounded else "contra"

        grounded_badge = (
            f'<span class="badge strong">{icon("check", 12)}Grounding Doğrulandı</span>'
            if is_grounded
            else f'<span class="badge contra">{icon("close", 12)}Grounding Uyarılı</span>'
        )

        created_raw = r.get("created_at") or ""
        created_str = (
            esc(created_raw[:19].replace("T", " ")) if created_raw else "Tarihsiz"
        )
        title_esc = esc(r.get("event_title") or "Olay")
        body_text = r.get("body") or ""
        body_esc = esc(body_text)
        action_esc = esc(r.get("user_action") or "üretildi")
        cited_len = len(r.get("cited_claim_ids") or [])
        event_id = r.get("event_id")


        search_blob = f"{title_esc} {body_esc} {angle_raw} {action_esc}".replace(
            '"', "&quot;"
        )

        card_body = f"""
        <div class="card" style="padding:var(--space-4)">
          <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:var(--space-3)">
            <div class="row tight">
              <span class="badge neutral" style="font-weight:var(--weight-semibold)">Açı: {esc(angle_raw.upper())}</span>
              <span class="mono subtle" style="font-size:var(--text-xs)">{created_str}</span>
              {grounded_badge}
            </div>
            <div class="row tight">
              <button class="btn sm ghost" type="button"{action_attrs("copy", body_text, "Yayınlanan metin")}>
                {icon("copy", 13)}<span>Kopyala</span>
              </button>
              <a class="btn sm ghost" href="/event/{event_id}">
                {icon("arrow-right", 13)}<span>Olay</span>
              </a>
            </div>
          </div>

          <h3 style="margin:0 0 var(--space-3);font-size:var(--text-lg)">
            <a class="plain" href="/event/{event_id}">{title_esc}</a>
          </h3>

          <div style="background:var(--color-surface-sunken);border:1px solid var(--color-border);padding:var(--space-3) var(--space-4);border-radius:var(--radius-md);margin-bottom:var(--space-3);font-family:var(--font-body);font-size:var(--text-sm);line-height:1.6;white-space:pre-wrap">
{body_esc}
          </div>

          <div class="row" style="font-size:var(--text-xs);color:var(--color-fg-subtle)">
            <span>Kanıt Dayanağı: <b>{cited_len} iddia</b></span>
            <span>· Editoryal Aksiyon: <b class="mono">{action_esc}</b></span>
            <span>· Kayıt No: <span class="mono">#{r.get("id")}</span></span>
          </div>
        </div>
        """

        cards_html.append(
            f'<div data-angle="{esc(angle_raw)}" data-search="{esc(search_blob)}">'
            + ruled(tone, card_body)
            + "</div>"
        )

    tabs_items = [('Tümü', 'all')] + [(a.upper(), a) for a in sorted(angles_present)]
    filter_tabs_html = '<div id="archive-tabs" class="segment">' + "".join(
        f'<button type="button"{" aria-current=\"true\"" if key == "all" else ""}'
        f"{action_attrs('filter-archive', key)}>{esc(lbl)}</button>"
        for lbl, key in tabs_items
    ) + "</div>"

    body = f"""
    {page_head(
        "Editoryal Yayın ve Kanıt Arşivi",
        lede="Yayınlanan her metnin zaman damgası, model sürümü ve dayandığı birincil kanıt kütüğü (Spec §14.4).",
        actions=search_input("archive-search", "Arşivde veya metinde ara…", action="search-archive"),
    )}

    {kpis_html}

    <div style="margin-bottom:var(--space-4)">
      {filter_tabs_html}
    </div>

    <div id="archive-list" class="stack" style="gap:var(--space-4)">
      {''.join(cards_html)}
    </div>
    <div id="archive-filter-empty" style="display:none;padding:var(--space-12);text-align:center">
      <p class="subtle">Arama ve filtre kriterinize uyan arşiv kaydı bulunamadı.</p>
    </div>
    """

    combined_js = ACTIVITY_JS + "\n" + _ARCHIVE_JS
    return HTMLResponse(
        page(
            "Yayın Arşivi",
            body,
            active="/archive",
            crumbs=(("Çalışma masası", None), ("Yayın Arşivi", None)),
            extra_js=combined_js,
        )
    )

