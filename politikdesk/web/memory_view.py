"""Siyasi Aktör Hafıza ve Kronoloji Ekranı (Spec v3.4 §7.3).

Belirli bir siyasi aktörün (bakan, milletvekili, parti sözcüsü vb.)
geçmiş beyanları, vaatleri ve bu beyanlara bağlı ilişki ağını sunar.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from politikdesk.political_memory import service as mem_service
from politikdesk.users import current_user_id, touch_last_seen
from politikdesk.web.ui import (
    ACTIVITY_JS,
    esc,
    page,
    page_head,
)

router = APIRouter(tags=["web"])


@router.get("/memory/{actor}", response_class=HTMLResponse)
def actor_memory_page(actor: str) -> HTMLResponse:
    """Aktör hafıza profili sayfası."""
    user_id = current_user_id()
    touch_last_seen(user_id)

    memory = mem_service.get_actor_memory(actor)

    head = page_head(
        f"Siyasi Hafıza: {actor}",

        lede=(
            f"Toplam {memory.total_claims} kayıtlı iddia, "
            f"{len(memory.promises)} vaat, {len(memory.attributions)} beyan."
        ),
    )

    disc_style = (
        "background: var(--pd-color-bg-subtle); "
        "border-left: 4px solid var(--pd-color-accent); "
        "padding: 0.85rem 1.25rem; font-size: 0.85rem; "
        "color: var(--pd-color-text-secondary);"
    )
    disclaimer_text = (
        "Bu profil sayfasındaki kayıtlar, yalnızca resmî kaynaklarda ve "
        "haber kütüğünde yer alan beyan ve olay eşleşmelerini sunar; "
        "kişisel kusur veya suçlama niteliği taşımaz."
    )
    disclaimer_html = f"""
    <div class="pd-panel" style="{disc_style}">
        <strong>Epistemik & Hukuki Çekince:</strong> {disclaimer_text}
    </div>
    """

    promises_html = []
    for p in memory.promises:
        promises_html.append(f"""
            <li style="margin-bottom: 0.75rem;">
                <strong>{esc(p.event_title)}</strong> ({esc(p.first_reported_at[:10])}):<br>
                <em>"{esc(p.claim_text)}"</em>
                <span class="pd-badge pd-badge--outline" style="margin-left: 0.5rem;">
                    {esc(p.evidence_status)}
                </span>
            </li>
        """)

    attributions_html = []
    for a in memory.attributions:
        attributions_html.append(f"""
            <li style="margin-bottom: 0.75rem;">
                <strong>{esc(a.event_title)}</strong> ({esc(a.first_reported_at[:10])}):<br>
                <em>"{esc(a.claim_text)}"</em>
                <span class="pd-badge pd-badge--outline" style="margin-left: 0.5rem;">
                    {esc(a.evidence_status)}
                </span>
            </li>
        """)

    relations_html = []
    for r in memory.relation_chains:
        rel_badge = f"<span class=\"pd-badge pd-badge--neutral\">{esc(r['relation'])}</span>"
        from_t = esc(r['from_title'])
        to_t = esc(r['to_title'])
        relations_html.append(f"""
            <li style="margin-bottom: 0.5rem;">
                <strong>{from_t}</strong> &rarr; {rel_badge} &rarr; <strong>{to_t}</strong>
            </li>
        """)

    header_border = (
        "margin-bottom: 1rem; border-bottom: 1px solid var(--pd-color-border); "
        "padding-bottom: 0.5rem;"
    )
    p_empty = '<li class="pd-text-muted">Kayıtlı vaat bulunmuyor.</li>'
    a_empty = '<li class="pd-text-muted">Kayıtlı beyan bulunmuyor.</li>'
    r_empty = '<li class="pd-text-muted">Kayıtlı olay ilişkisi bulunmuyor.</li>'

    p_list = ''.join(promises_html) if promises_html else p_empty
    a_list = ''.join(attributions_html) if attributions_html else a_empty
    r_list = ''.join(relations_html) if relations_html else r_empty

    p_count = len(memory.promises)
    a_count = len(memory.attributions)
    r_count = len(memory.relation_chains)

    content = f"""
    <div class="pd-stack pd-stack--lg">
        {head}
        {disclaimer_html}

        <div class="pd-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
            <div class="pd-panel">
                <h3 style="{header_border}">Kayıtlı Vaatler ({p_count})</h3>
                <ul>{p_list}</ul>
            </div>

            <div class="pd-panel">
                <h3 style="{header_border}">Beyan ve Açıklamalar ({a_count})</h3>
                <ul>{a_list}</ul>
            </div>
        </div>

        <div class="pd-panel">
            <h3 style="{header_border}">İlişki ve Çelişki Ağları ({r_count})</h3>
            <ul>{r_list}</ul>
        </div>
    </div>
    """



    html = page(
        f"Hafıza: {actor}",
        content,
        active="/memory",
        extra_js=ACTIVITY_JS,
    )
    return HTMLResponse(html)
