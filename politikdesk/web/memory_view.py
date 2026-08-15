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
    esc,
    page,
    page_head,
)

router = APIRouter(tags=["web"])


@router.get("/memory", response_class=HTMLResponse)
@router.get("/hafiza", response_class=HTMLResponse)
def memory_directory_page() -> HTMLResponse:
    """Siyasi Hafıza Dizin ve Aktör Listesi ana sayfası."""
    user_id = current_user_id()
    touch_last_seen(user_id)

    actors = mem_service.list_tracked_actors()

    head = page_head(
        "Siyasi Hafıza Masası",
        lede=(
            "Siyasi aktörlerin, bakanların ve parti sözcülerinin geçmiş beyanları, "
            "vaatleri ve teyit zincirleri."
        ),
    )

    disc_style = (
        "background: var(--pd-color-bg-subtle); "
        "border-left: 4px solid var(--pd-color-accent); "
        "padding: 0.85rem 1.25rem; font-size: 0.85rem; "
        "color: var(--pd-color-text-secondary);"
    )
    disclaimer_text = (
        "Siyasi Hafıza kayıtları, kamuoyuna açık resmî tutanaklar ve "
        "haber kaynaklarından derlenen beyan ve olay eşleşmelerini sunar; "
        "kişisel suçlama niteliği taşımaz."
    )
    disclaimer_html = f"""
    <div class="pd-panel" style="{disc_style}">
        <strong>Epistemik & Hukuki Çekince:</strong> {disclaimer_text}
    </div>
    """

    actors_html = []
    if not actors:
        empty_text = (
            "Henüz kayıtlı aktör profili bulunmuyor. "
            "Ingestion akışı çalıştıkça aktörler listelenecektir."
        )
        actors_html.append(f"""
            <div class="pd-panel pd-text-muted" style="text-align: center; padding: 2rem;">
                {empty_text}
            </div>
        """)
    else:
        cards = []
        for a in actors:
            name_esc = esc(a["name"])
            encoded_name = urllib.parse.quote(a["name"])
            badge = ""
            if a.get("is_key_entity"):
                badge = '<span class="pd-badge pd-badge--neutral">Kilit Aktör</span>'
            type_label = (
                "Kurum / Parti" if a.get("entity_type") == "institution" else "Siyasi Aktör"
            )
            card_style = (
                "text-decoration: none; color: inherit; display: block; "
                "transition: border-color 0.2s;"
            )
            hdr_style = (
                "display: flex; justify-content: space-between; "
                "align-items: center; margin-bottom: 0.5rem;"
            )
            lbl_style = "font-size: 0.8rem; color: var(--pd-color-text-muted);"
            h3_style = "margin: 0; font-size: 1.1rem; color: var(--pd-color-accent);"
            p_style = (
                "margin: 0.5rem 0 0 0; font-size: 0.85rem; "
                "color: var(--pd-color-text-secondary);"
            )
            cards.append(f"""
                <a href="/memory/{encoded_name}" class="pd-panel" style="{card_style}">
                    <div style="{hdr_style}">
                        <span style="{lbl_style}">{type_label}</span>
                        {badge}
                    </div>
                    <h3 style="{h3_style}">{name_esc}</h3>
                    <p style="{p_style}">
                        Geçmiş beyanları, vaatleri ve çelişki ağlarını incele &rarr;
                    </p>
                </a>
            """)
        grid_style = (
            "display: grid; grid-template-columns: "
            "repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem;"
        )
        actors_html.append(f"""
            <div class="pd-grid" style="{grid_style}">
                {''.join(cards)}
            </div>
        """)

    content = f"""
    <div class="pd-stack pd-stack--lg">
        {head}
        {disclaimer_html}
        {''.join(actors_html)}
    </div>
    """

    html = page(
        "Siyasi Hafıza",
        content,
        active="/memory",
        extra_js=ACTIVITY_JS,
    )
    return HTMLResponse(html)


@router.get("/memory/{actor}", response_class=HTMLResponse)
@router.get("/hafiza/{actor}", response_class=HTMLResponse)
def actor_memory_page(actor: str) -> HTMLResponse:
    """Aktör hafıza profili sayfası."""
    user_id = current_user_id()
    touch_last_seen(user_id)

    decoded_actor = urllib.parse.unquote(actor)
    memory = mem_service.get_actor_memory(decoded_actor)

    head = page_head(
        f"Siyasi Hafıza: {decoded_actor}",
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
        f"Hafıza: {decoded_actor}",
        content,
        active="/memory",
        extra_js=ACTIVITY_JS,
    )
    return HTMLResponse(html)
