"""Siyasi Aktör Hafıza ve Kronoloji Ekranı (Spec v3.4 §7.3 · B-15).

Belirli bir siyasi aktörün (bakan, milletvekili, parti sözcüsü vb.)
geçmiş beyanları, vaatleri ve bu beyanlara bağlı ilişki ağını sunar.
"""

from __future__ import annotations

import urllib.parse

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from politikdesk.political_memory import service as mem_service
from politikdesk.users import current_user_id, touch_last_seen
from politikdesk.web.ui import (
    ACTIVITY_JS,
    button,
    card,
    empty_state,
    esc,
    icon,
    kpi,
    notice,
    page,
    page_head,
    ruled,
    search_input,
    status_badge,
)
from politikdesk.web.ui import format as fmt

router = APIRouter(tags=["web"])

_DIRECTORY_JS = """
(function(){
  window.pdSearchActors = function(query) {
    var q = query.toLowerCase().trim();
    var cards = document.querySelectorAll('#actor-grid [data-actor-name]');
    var visible = 0;
    cards.forEach(function(c) {
      var name = (c.dataset.actorName || '').toLowerCase();
      var type = (c.dataset.actorType || '').toLowerCase();
      if (!q || name.indexOf(q) !== -1 || type.indexOf(q) !== -1) {
        c.style.display = '';
        visible++;
      } else {
        c.style.display = 'none';
      }
    });
    var emptyEl = document.getElementById('actor-search-empty');
    if (emptyEl) {
      emptyEl.style.display = (visible === 0 && cards.length > 0) ? '' : 'none';
    }
  };
})();
"""

_ACTOR_TIMELINE_JS = """
(function(){
  var currentFilter = 'all';

  window.pdFilterTimeline = function(kind, btn) {
    currentFilter = kind;
    document.querySelectorAll('#timeline-tabs a').forEach(function(a) {
      a.removeAttribute('aria-current');
    });
    if (btn) btn.setAttribute('aria-current', 'true');

    var items = document.querySelectorAll('#timeline-items [data-claim-type]');
    var visible = 0;
    items.forEach(function(it) {
      var type = it.dataset.claimType;
      var rel = it.dataset.rel;
      var match = (currentFilter === 'all') ||
        (currentFilter === 'promise' && type === 'promise') ||
        (currentFilter === 'attribution' && type !== 'promise') ||
        (currentFilter === 'contra' && (rel === 'contradicts' || rel === 'fails'));

      if (match) {
        it.style.display = '';
        visible++;
      } else {
        it.style.display = 'none';
      }
    });
  };
})();
"""


@router.get("/memory", response_class=HTMLResponse)
@router.get("/hafiza", response_class=HTMLResponse)
def memory_directory_page() -> HTMLResponse:
    """Siyasi Hafıza Dizin ve Aktör Listesi ana sayfası."""
    try:
        user_id = current_user_id()
        touch_last_seen(user_id)
        actors = mem_service.list_tracked_actors()
    except Exception:  # noqa: BLE001
        actors = []

    total_actors = len(actors)
    key_actors = sum(1 for a in actors if a.get("is_key_entity"))
    institutions = sum(1 for a in actors if a.get("entity_type") == "institution")
    individuals = total_actors - institutions

    kpis_html = f"""
    <div class="kpis" style="margin-bottom:var(--space-6)">
      {kpi("Takip Edilen Aktör", fmt.number(total_actors), unit="profil", icon_name="identity")}
      {kpi("Kilit Siyasi Aktör", fmt.number(key_actors), unit="aktör", icon_name="shield")}
      {kpi("Bakanlık / Kurum", fmt.number(institutions), unit="kurum", icon_name="pipeline")}
      {kpi("Siyasi Temsilci", fmt.number(individuals), unit="kişi", icon_name="clock")}
    </div>
    """

    disclaimer_text = (
        "Siyasi Hafıza kayıtları, kamuoyuna açık resmî tutanaklar ve "
        "haber kaynaklarından derlenen beyan ve olay eşleşmelerini sunar; "
        "kişisel suçlama niteliği taşımaz."
    )
    disclaimer_html = notice(
        f"<p><b>Epistemik & Hukuki Çekince:</b> {esc(disclaimer_text)}</p>"
    )

    if not actors:
        body = f"""
        {page_head("Siyasi Hafıza Masası", lede="Siyasi aktörlerin, bakanların ve parti sözcülerinin geçmiş beyanları, vaatleri ve teyit zincirleri.")}
        {disclaimer_html}
        <div style="margin-top:var(--space-6)">
        {card(empty_state(
            "Henüz kayıtlı aktör profili bulunmuyor",
            "Haber ve tutanak akışı çalıştıkça aktörler ve siyasi hafıza kütüğü otomatik doldurulacaktır.",
            action=button("Gündeme dön", href="/feed", variant="primary"),
            icon_name="identity",
        ))}
        </div>
        """
        return HTMLResponse(
            page(
                "Siyasi Hafıza",
                body,
                active="/memory",
                crumbs=(("Çalışma masası", None), ("Siyasi Hafıza", None)),
                extra_js=ACTIVITY_JS,
            )
        )

    cards = []
    for a in actors:
        name_raw = a.get("name") or "İsimsiz Aktör"
        name_esc = esc(name_raw)
        encoded_name = urllib.parse.quote(name_raw)
        is_key = bool(a.get("is_key_entity"))
        is_inst = a.get("entity_type") == "institution"
        type_label = "Kurum / Parti" if is_inst else "Siyasi Aktör"

        badge_html = (
            f'<span class="badge strong">{icon("shield", 12)}Kilit Aktör</span>'
            if is_key
            else f'<span class="badge neutral">{type_label}</span>'
        )

        card_html = f"""
        <div class="card" style="height:100%;display:flex;flex-direction:column;justify-content:space-between;transition:border-color var(--dur-hover) var(--ease-out)">
          <div>
            <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:var(--space-2)">
              <span class="subtle" style="font-size:var(--text-xs)">{type_label}</span>
              {badge_html}
            </div>
            <h3 style="margin:0 0 var(--space-2);font-size:var(--text-lg);color:var(--color-fg)">
              {name_esc}
            </h3>
            <p class="subtle" style="margin:0;font-size:var(--text-sm)">
              Geçmiş beyanları, vaatleri ve teyit ağlarını incele
            </p>
          </div>
          <div style="margin-top:var(--space-4);display:flex;align-items:center;justify-content:flex-end">
            <span class="btn sm ghost" style="color:var(--color-accent)">
              Profili Aç {icon("arrow-right", 14)}
            </span>
          </div>
        </div>
        """
        cards.append(
            f'<a href="/memory/{encoded_name}" class="plain" data-actor-name="{name_esc}" data-actor-type="{esc(type_label)}">'
            f"{card_html}</a>"
        )

    body = f"""
    {page_head(
        "Siyasi Hafıza Masası",
        lede="Siyasi aktörlerin, bakanların ve parti sözcülerinin geçmiş beyanları, kamuoyu vaatleri ve teyit zincirleri.",
        actions=search_input("actor-search", "Aktör veya kurum ara…", oninput="pdSearchActors(this.value)"),
    )}
    {kpis_html}
    <div style="margin-bottom:var(--space-6)">{disclaimer_html}</div>

    <div id="actor-grid" class="grid-auto">
      {''.join(cards)}
    </div>
    <div id="actor-search-empty" style="display:none;padding:var(--space-12);text-align:center">
      <p class="subtle">Arama kriterinize uygun siyasi aktör bulunamadı.</p>
    </div>
    """

    combined_js = ACTIVITY_JS + "\n" + _DIRECTORY_JS
    return HTMLResponse(
        page(
            "Siyasi Hafıza",
            body,
            active="/memory",
            crumbs=(("Çalışma masası", None), ("Siyasi Hafıza", None)),
            extra_js=combined_js,
        )
    )


@router.get("/memory/{actor}", response_class=HTMLResponse)
@router.get("/hafiza/{actor}", response_class=HTMLResponse)
def actor_memory_page(actor: str) -> HTMLResponse:
    """Aktör hafıza ve interaktif zaman tüneli sayfası."""
    user_id = current_user_id()
    touch_last_seen(user_id)

    decoded_actor = urllib.parse.unquote(actor)
    memory = mem_service.get_actor_memory(decoded_actor)

    p_count = len(memory.promises)
    r_count = len(memory.relation_chains)
    fulfilled_count = sum(
        1 for p in memory.promises if p.relation_to_current in ("fulfils", "fulfilled")
    )
    contra_count = sum(
        1 for p in memory.promises if p.relation_to_current in ("contradicts", "fails")
    )
    pending_count = p_count - (fulfilled_count + contra_count)
    fulfil_rate = round(fulfilled_count / p_count * 100) if p_count > 0 else 0

    head = page_head(
        f"Siyasi Hafıza: {decoded_actor}",
        lede=f"Toplam {memory.total_claims} kayıtlı iddia · {p_count} vaat · %{fulfil_rate} gerçekleşme oranı · {r_count} ilişki bağı.",
        actions=button("Tüm Aktörler", href="/memory", icon_name="identity"),
    )

    disclaimer_text = (
        "Bu profil sayfasındaki kayıtlar, yalnızca resmî kaynaklarda ve "
        "haber kütüğünde yer alan beyan ve olay eşleşmelerini sunar; "
        "deterministik kanıt motoru tarafından şeffaf olarak arşivlenir."
    )
    disclaimer_html = notice(
        f"<p><b>Epistemik & Hukuki Çekince:</b> {esc(disclaimer_text)}</p>"
    )

    kpis_html = f"""
    <div class="kpis" style="margin-bottom:var(--space-6)">
      {kpi("Gerçekleşme Oranı", f"%{fulfil_rate}", unit="vaat uyumu", icon_name="promise")}
      {kpi("Gerçekleşen Vaat", fmt.number(fulfilled_count), unit="icraat", icon_name="check")}
      {kpi("Çelişen / Gerçekleşmeyen", fmt.number(contra_count), unit="kayıt", icon_name="warning", higher_is_better=False)}
      {kpi("Takipteki Süreç", fmt.number(pending_count), unit="vaat", icon_name="clock")}
    </div>
    """

    all_entries = sorted(
        memory.promises + memory.attributions,
        key=lambda e: e.first_reported_at,
        reverse=True,
    )

    timeline_items = []
    for entry in all_entries:
        is_promise = entry.claim_type == "promise"
        type_badge = (
            f'<span class="badge accent">{icon("promise", 12)}Siyasi Vaat</span>'
            if is_promise
            else f'<span class="badge neutral">{icon("identity", 12)}Siyasi Beyan</span>'
        )

        st_badge = status_badge(entry.evidence_status)
        rel = entry.relation_to_current or ""
        rel_badge = (
            f'<span class="badge contra">{icon("warning", 12)}{esc(rel)}</span>'
            if rel in ("contradicts", "fails")
            else (
                f'<span class="badge strong">{icon("check", 12)}{esc(rel)}</span>'
                if rel in ("fulfils", "fulfilled")
                else (f'<span class="badge outline">{esc(rel)}</span>' if rel else "")
            )
        )

        date_str = (
            esc(entry.first_reported_at[:10])
            if entry.first_reported_at
            else "Tarihsiz"
        )
        feed_link = f"/feed?q={urllib.parse.quote(entry.event_title)}"
        tone = "contra" if rel in ("contradicts", "fails") else ("strong" if rel in ("fulfils", "fulfilled") else "unverified")

        item_body = f"""
        <div class="card" style="padding:var(--space-3) var(--space-4);margin-bottom:var(--space-3)">
          <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:var(--space-2)">
            <div class="row tight">
              <span class="mono subtle" style="font-size:var(--text-xs)">{date_str}</span>
              {type_badge}
              {st_badge}
              {rel_badge}
            </div>
            <a class="btn sm ghost" href="{feed_link}">{icon("arrow-right", 12)}Olay</a>
          </div>
          <h4 style="margin:0 0 var(--space-2);font-size:var(--text-base)">
            <a class="plain" href="{feed_link}">{esc(entry.event_title)}</a>
          </h4>
          <p class="claim-text" style="margin:0;font-size:var(--text-sm);font-style:italic;color:var(--color-fg-muted)">
            “{esc(entry.claim_text)}”
          </p>
        </div>
        """

        timeline_items.append(
            f'<div data-claim-type="{esc(entry.claim_type)}" data-rel="{esc(rel)}">'
            + ruled(tone, item_body)
            + "</div>"
        )

    timeline_html = (
        "".join(timeline_items)
        if timeline_items
        else '<p class="subtle" style="padding:var(--space-6);text-align:center">Kayıtlı olay veya beyan bulunmuyor.</p>'
    )

    filter_tabs_html = f"""
    <div id="timeline-tabs" class="segment">
      <a href="javascript:void(0)" aria-current="true" onclick="pdFilterTimeline('all', this)">Tümü ({len(all_entries)})</a>
      <a href="javascript:void(0)" onclick="pdFilterTimeline('promise', this)">Vaatler ({p_count})</a>
      <a href="javascript:void(0)" onclick="pdFilterTimeline('attribution', this)">Beyanlar ({len(memory.attributions)})</a>
      <a href="javascript:void(0)" onclick="pdFilterTimeline('contra', this)">Çelişkiler ({contra_count})</a>
    </div>
    """

    relations_rows = []
    for r in memory.relation_chains:
        rel_str = r.get("relation", "ilişkili")
        badge = (
            f'<span class="badge contra">{esc(rel_str)}</span>'
            if rel_str in ("contradicts", "fails")
            else f'<span class="badge strong">{esc(rel_str)}</span>'
        )
        relations_rows.append(
            f'<li style="margin-bottom:var(--space-3);font-size:var(--text-sm);list-style:none">'
            f'<div style="font-weight:var(--weight-medium);margin-bottom:2px">{esc(r["from_title"])}</div>'
            f'<div style="margin:4px 0">{badge}</div>'
            f'<div class="subtle" style="font-size:var(--text-xs)">{esc(r["to_title"])}</div>'
            f"</li>"
        )

    relations_content = (
        f'<ul style="margin:0;padding:0">{"".join(relations_rows)}</ul>'
        if relations_rows
        else '<p class="subtle" style="margin:0">Kayıtlı olay ilişkisi bulunmuyor.</p>'
    )

    from politikdesk.political_memory.stance_shift import detect_stance_shifts_from_memory
    from politikdesk.web.ui.charts import render_knowledge_graph

    # Bilgi grafı düğüm ve kenarları
    graph_nodes = [{"id": "main_actor", "label": decoded_actor, "type": "actor"}]
    graph_links = []
    for i, rel_item in enumerate(memory.relation_chains[:8]):
        to_id = f"ev_{rel_item.get('to_event_id', i)}"
        to_title = str(rel_item.get("to_title", f"Olay #{i}"))
        graph_nodes.append({"id": to_id, "label": to_title[:18], "type": "event"})
        graph_links.append(
            {
                "source": "main_actor",
                "target": to_id,
                "relation": str(rel_item.get("relation", "precedes")),
                "label": str(rel_item.get("relation", "")),
            }
        )

    graph_html = (
        card(
            render_knowledge_graph(graph_nodes, graph_links, width=760, height=280),
            title="Etkileşimli İlişki ve Duruş Grafı",
        )
        if len(graph_nodes) > 1
        else ""
    )

    # Söylem Değişiklikleri ve Zıtlık Radarı
    shifts = detect_stance_shifts_from_memory(memory)
    shift_cards = []
    for s in shifts:
        shift_tone = "bad" if s.shift_type in ("reversal", "broken_promise") else "warn"
        type_label = {
            "reversal": "180° Zıt Beyan",
            "broken_promise": "Tutulmayan Vaat",
            "numeric_divergence": "Sayısal Sapma",
            "policy_pivot": "Politika Değişimi",
        }.get(s.shift_type, s.shift_type)

        shift_cards.append(
            f'<div class="card" style="padding:var(--space-3) var(--space-4);margin-bottom:var(--space-2);border-left:3px solid var(--color-border-strong)">'
            f'<div class="row tight" style="justify-content:space-between;margin-bottom:6px">'
            f'<span class="badge {shift_tone}">{esc(type_label)}</span>'
            f'<span class="subtle mono" style="font-size:var(--text-xs)">{s.time_span_days} gün fark</span>'
            f'</div>'
            f'<div style="font-size:var(--text-sm);margin-bottom:4px"><b>Önceki:</b> “{esc(s.earlier_claim_text)}”</div>'
            f'<div style="font-size:var(--text-sm);color:var(--color-fg-muted)"><b>Sonraki:</b> “{esc(s.later_claim_text)}”</div>'
            f'</div>'
        )

    shifts_html = card(
        "".join(shift_cards) if shift_cards else '<p class="subtle" style="margin:0">Belirgin bir söylem değişikliği veya zıtlık tespit edilmedi.</p>',
        title=f"Söylem Değişikliği ve Zıtlık Radarı · {len(shifts)}",
    )

    body = f"""
    {head}
    {kpis_html}
    <div style="margin-bottom:var(--space-6)">{disclaimer_html}</div>
    {f'<div style="margin-bottom:var(--space-6)">{graph_html}</div>' if graph_html else ''}

    <div class="split">
      <div class="stack" style="gap:var(--space-4)">
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:var(--space-2)">
          <h3 style="font-size:var(--text-lg)">Kronolojik Zaman Tüneli</h3>
          {filter_tabs_html}
        </div>
        <div id="timeline-items" class="stack" style="gap:var(--space-2)">
          {timeline_html}
        </div>
      </div>

      <div class="stack">
        {shifts_html}
        {card(
            relations_content,
            title=f"İlişki ve Duruş Ağı · {r_count}",
        )}
      </div>
    </div>
    """

    combined_js = ACTIVITY_JS + "\n" + _ACTOR_TIMELINE_JS
    return HTMLResponse(
        page(
            f"Hafıza: {decoded_actor}",
            body,
            active="/memory",
            crumbs=(("Çalışma masası", None), ("Siyasi Hafıza", "/memory"), (decoded_actor, None)),
            extra_js=combined_js,
        )
    )


