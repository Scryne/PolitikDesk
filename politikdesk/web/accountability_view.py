"""Hesap Sor (Accountability Digest) Ekranı (Spec v3.4 §8.3, §14.1).

Siyasi aktörlerin geçmiş beyanları ve vaatleri ile güncel Meclis oylamaları,
bütçe harcamaları ve Sayıştay denetim bulgularını karşılaştıran
editoryal hesap verebilirlik analiz masası.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from politikdesk.political_memory import service as mem_service
from politikdesk.political_memory.accountability import LEGAL_DISCLAIMER
from politikdesk.users import current_user_id, touch_last_seen
from politikdesk.web.ui import (
    ACTIVITY_JS,
    action_attrs,
    button,
    card,
    empty_state,
    esc,
    icon,
    kpi,
    notice,
    page,
    page_head,
    panel,
    ruled,
    search_input,
    status_badge,
)
from politikdesk.web.ui import format as fmt
from politikdesk.web.ui.components import relation_label

router = APIRouter(tags=["web"])

EPISTEMIC_BADGES: dict[str, tuple[str, str]] = {
    "verified": ("Doğrulanmış Atıf", "strong"),
    "supported": ("Kanıtla Desteklenen", "partial"),
    "inferred": ("Olası İlişki", "neutral"),
    "unresolved": ("Belirsiz", "unverified"),
    "unmatched": ("Eşleşme bekliyor", "neutral"),
}


def _relation_tone(rel: str, status: str) -> str:
    if rel in ("contradicts", "fails"):
        return "contra"
    if status == "verified":
        return "strong"
    if status == "supported":
        return "partial"
    return "unverified"


_ACCOUNTABILITY_JS = """
(function(){
  var currentFilter = 'all';
  var currentQuery = '';

  function applyFilters() {
    var cards = document.querySelectorAll('#accountability-list [data-status]');
    var visible = 0;
    var q = currentQuery.toLowerCase().trim();

    cards.forEach(function(c) {
      var status = c.dataset.status;
      var rel = c.dataset.rel;
      var text = (c.dataset.search || '').toLowerCase();
      var matchesFilter = (currentFilter === 'all') ||
        (currentFilter === 'verified' && status === 'verified') ||
        (currentFilter === 'supported' && status === 'supported') ||
        (currentFilter === 'contra' && (rel === 'contradicts' || rel === 'fails')) ||
        (currentFilter === 'inferred' && (status === 'inferred' || status === 'unresolved')) ||
        (currentFilter === 'unmatched' && status === 'unmatched');
      var matchesText = !q || text.indexOf(q) !== -1;

      if (matchesFilter && matchesText) {
        c.style.display = '';
        visible++;
      } else {
        c.style.display = 'none';
      }
    });

    var emptyEl = document.getElementById('accountability-filter-empty');
    if (emptyEl) {
      emptyEl.style.display = (visible === 0 && cards.length > 0) ? '' : 'none';
    }
  }

  window.pdFilterAcc = function(filterKey, btn) {
    currentFilter = filterKey;
    document.querySelectorAll('#accountability-tabs button').forEach(function(b) {
      b.removeAttribute('aria-current');
    });
    if (btn) btn.setAttribute('aria-current', 'true');
    applyFilters();
  };

  // Dağıtıcı `input` olayında (öğe, olay) geçer; arama metni öğeden okunur.
  window.pdSearchAcc = function(el) {
    currentQuery = el.value;
    applyFilters();
  };

  window.pdAction('filter-acc', window.pdFilterAcc);
  window.pdAction('search-acc', window.pdSearchAcc);
})();
"""


@router.get("/accountability", response_class=HTMLResponse)
@router.get("/hesap-sor", response_class=HTMLResponse)
def accountability_page() -> HTMLResponse:
    try:
        user_id = current_user_id()
        touch_last_seen(user_id)
        digest = mem_service.get_accountability_digest()
    except Exception:  # noqa: BLE001
        digest = []


    # Epistemik durum İLİŞKİNİN durumudur (`event_relations.status`); ilişkisi
    # olmayan vaat "eşleşme bekliyor"dur, doğrulanmış/desteklenen sayılmaz.
    def _epistemic(item: dict[str, Any]) -> str:
        if not item.get("relation"):
            return "unmatched"
        return str(item.get("relation_status") or "unresolved")

    total_count = len(digest)
    matched_count = sum(1 for item in digest if item.get("relation"))
    verified_count = sum(1 for item in digest if _epistemic(item) == "verified")
    supported_count = sum(1 for item in digest if _epistemic(item) == "supported")
    contra_count = sum(
        1 for item in digest if item.get("relation") in ("contradicts", "fails")
    )
    inferred_count = sum(
        1 for item in digest if _epistemic(item) in ("inferred", "unresolved")
    )
    unmatched_count = total_count - matched_count

    kpis_html = f"""
    <div class="kpis" style="margin-bottom:var(--space-6)">
      {kpi("Çapraz eşleşme", fmt.number(matched_count), unit=f"/ {fmt.number(total_count)} vaat", icon_name="accountability")}
      {kpi("Doğrulanmış Atıf", fmt.number(verified_count), unit="vaka", icon_name="check")}
      {kpi("Desteklenen Kanıt", fmt.number(supported_count), unit="kayıt", icon_name="shield")}
      {kpi("Tespit Edilen Çelişki", fmt.number(contra_count), unit="olay", icon_name="warning", higher_is_better=False)}
    </div>
    """

    disclaimer_html = notice(
        f"<p><b>Epistemik & Hukuki Çekince:</b> {esc(LEGAL_DISCLAIMER)}</p>"
    )


    if not digest:
        body = f"""
        {page_head("Hesap Sor: Editoryal Hesap Verebilirlik", lede="Geçmiş vaatler, TBMM oylama tutanakları ve Sayıştay kamu zararı bulguları arasındaki çapraz eşleme.")}
        {disclaimer_html}
        <div style="margin-top:var(--space-6)">
        {card(empty_state(
            "Henüz hesap verebilirlik analizi için eşleşen kayıt bulunmuyor",
            "Sayıştay raporları, TBMM komisyon tutanakları ve meclis oylamaları işlendikçe çapraz denetim bulguları burada listelenecektir.",
            action=button("Gündeme dön", href="/feed", variant="primary"),
            icon_name="accountability",
        ))}
        </div>
        """
        return HTMLResponse(
            page(
                "Hesap Sor",
                body,
                active="/accountability",
                crumbs=(("Çalışma masası", None), ("Hesap Sor", None)),
                extra_js=ACTIVITY_JS,
            )
        )

    cards_html = []
    for item in digest:
        status_key = _epistemic(item)
        badge_label, badge_token = EPISTEMIC_BADGES.get(
            status_key, (status_key, "neutral")
        )
        confidence = item.get("confidence")
        conf_text = (
            fmt.percent(float(confidence) * 100) if isinstance(confidence, int | float) else fmt.EMPTY
        )
        payload = item.get("evidence_payload") or {}
        breakdown = payload.get("score_breakdown") or {}
        target_inst_or_actor = (
            payload.get("target_institution") or payload.get("target_actor") or "Genel"
        )
        target_title_esc = esc(payload.get("target_title", "Belirtilmedi"))

        rel = item.get("relation") or ""
        tone = _relation_tone(rel, status_key)
        reported_date = esc(fmt.full_date(item.get("reported_at")))
        speaker_known = item.get("speaker")
        speaker_raw = speaker_known or "Konuşan belirtilmedi"
        speaker_esc = esc(speaker_raw)
        speaker_encoded = urllib.parse.quote(speaker_raw)
        event_title_esc = esc(item.get("event_title") or "Olay")
        promise_text_esc = esc(item.get("promise_text") or "")
        ev_status_html = status_badge(str(item.get("evidence_status") or "unverified"), size=12)
        profile_btn = (
            f'<a class="btn sm ghost" href="/memory/{speaker_encoded}">'
            f'{icon("clock", 14)}Aktör profili &rarr;</a>'
            if speaker_known
            else ""
        )

        drawer_body = f"""
        <table style="margin-top:var(--space-2)">
          <thead><tr><th>Eşleme Boyutu</th><th class="num">Skor</th></tr></thead>
          <tbody>
            <tr><td>Hedef Olay</td><td class="num">{target_title_esc}</td></tr>
            <tr><td>Hedef Kurum / Aktör</td><td class="num">{esc(target_inst_or_actor)}</td></tr>
            <tr><td>Kurumsal Eşleşme Skoru</td><td class="num mono">{esc(str(breakdown.get("institution_score", "—")))}</td></tr>
            <tr><td>Konu Uyumu Skoru</td><td class="num mono">{esc(str(breakdown.get("topic_score", "—")))}</td></tr>
            <tr><td>Zamanlama Yakınlığı</td><td class="num mono">{esc(str(breakdown.get("temporal_score", "—")))}</td></tr>
            <tr><td>Varlık / Aktör Doğrulaması</td><td class="num mono">{esc(str(breakdown.get("entity_score", "—")))}</td></tr>
          </tbody>
        </table>
        """
        drawer_summary = (
            f'{icon("shield", 14)}<span>Eşleme skorunun kırılımı '
            f'<b class="num">(güven {esc(conf_text)})</b></span>'
            f'<span class="subtle">— ayrıntı</span>'
        )
        drawer_panel = (
            panel(drawer_summary, drawer_body, cls="quiet")
            if rel
            else '<p class="subtle" style="margin:0;font-size:var(--text-xs)">'
            "Bu vaat henüz bir oylama, karar ya da denetim bulgusuyla eşleşmedi; "
            "eşleşme kurulduğunda skor kırılımı burada görünür.</p>"
        )

        search_blob = f"{speaker_raw} {event_title_esc} {promise_text_esc} {target_inst_or_actor} {target_title_esc}".replace(
            '"', "&quot;"
        )

        card_content = f"""
        <div class="card" style="padding:var(--space-4)">
          <div class="row" style="justify-content:space-between;align-items:flex-start">
            <div class="row tight">
              <span class="badge neutral" style="font-weight:var(--weight-semibold)">{speaker_esc}</span>
              <span class="badge {badge_token}">{esc(badge_label)}</span>
              <span class="badge outline">{reported_date}</span>
            </div>
            {profile_btn}
          </div>
          <h2 class="h3" style="margin:var(--space-3) 0 var(--space-2);font-size:var(--text-lg)">
            {event_title_esc}
          </h2>
          <p class="claim-text" style="font-size:var(--text-base);font-style:italic;color:var(--color-fg-muted);margin:0 0 var(--space-3)">
            “{promise_text_esc}”
          </p>
          <div class="row" style="font-size:var(--text-xs);color:var(--color-fg-subtle);margin-bottom:var(--space-3)">
            <span>İlişki: <b>{esc(relation_label(rel or None))}</b></span>
            <span>· Vaadin kanıt durumu: {ev_status_html}</span>
            <span>· Eşleme güveni: <b class="num">{esc(conf_text)}</b></span>
          </div>
          {drawer_panel}
        </div>
        """

        cards_html.append(
            f'<div data-status="{esc(status_key)}" data-rel="{esc(rel)}" data-search="{esc(search_blob)}">'
            + ruled(tone, card_content)
            + "</div>"
        )

    filter_tabs_html = f"""
    <div id="accountability-tabs" class="segment">
      <button type="button" aria-current="true"{action_attrs("filter-acc", "all")}>Tümü ({total_count})</button>
      <button type="button"{action_attrs("filter-acc", "verified")}>Doğrulanmış ({verified_count})</button>
      <button type="button"{action_attrs("filter-acc", "supported")}>Desteklenen ({supported_count})</button>
      <button type="button"{action_attrs("filter-acc", "contra")}>Çelişkiler ({contra_count})</button>
      <button type="button"{action_attrs("filter-acc", "inferred")}>Olası ilişki ({inferred_count})</button>
      <button type="button"{action_attrs("filter-acc", "unmatched")}>Eşleşme bekleyen ({unmatched_count})</button>
    </div>
    """

    body = f"""
    {page_head(
        "Hesap Sor: Editoryal Hesap Verebilirlik",
        lede="Geçmiş vaatler, TBMM oylama tutanakları ve Sayıştay kamu zararı bulguları arasındaki çapraz eşleme ve nedensellik kütüğü.",
        actions=search_input("acc-search", "Vaka, aktör veya kurum ara…", action="search-acc"),
    )}

    {kpis_html}
    <div style="margin-bottom:var(--space-4)">{disclaimer_html}</div>

    <div style="margin-bottom:var(--space-4)">{filter_tabs_html}</div>

    <div id="accountability-list" class="stack" style="gap:var(--space-4)">
      {''.join(cards_html)}
    </div>
    <div id="accountability-filter-empty" style="display:none;padding:var(--space-12);text-align:center">
      <p class="subtle">Arama ve filtre kriterlerine uyan vaka kaydı bulunamadı.</p>
    </div>
    """

    combined_js = ACTIVITY_JS + "\n" + _ACCOUNTABILITY_JS
    return HTMLResponse(
        page(
            "Hesap Sor",
            body,
            active="/accountability",
            crumbs=(("Çalışma masası", None), ("Hesap Sor", None)),
            extra_js=combined_js,
        )
    )

