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
                "margin: 0.5rem 0 0 0; font-size: 0.85rem; color: var(--pd-color-text-secondary);"
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
                {"".join(cards)}
            </div>
        """)

    content = f"""
    <div class="pd-stack pd-stack--lg">
        {head}
        {disclaimer_html}
        {"".join(actors_html)}
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
    """Aktör hafıza ve interaktif zaman tüneli sayfası."""
    user_id = current_user_id()
    touch_last_seen(user_id)

    decoded_actor = urllib.parse.unquote(actor)
    memory = mem_service.get_actor_memory(decoded_actor)

    # Vaat gerçekleşme istatistikleri
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
        f"Siyasi Hafıza & Zaman Tüneli: {decoded_actor}",
        lede=(
            f"Toplam {memory.total_claims} kayıtlı iddia · {p_count} vaat "
            f"· %{fulfil_rate} gerçekleşme oranı · {r_count} ilişki bağı."
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
        "deterministik kanıt motoru tarafından şeffaf olarak arşivlenir."
    )
    disclaimer_html = f"""
    <div class="pd-panel" style="{disc_style}">
        <strong>Epistemik & Hukuki Çekince:</strong> {disclaimer_text}
    </div>
    """

    grid_style = (
        "display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;"
    )
    panel_style = "text-align: center; padding: 1.25rem;"

    # Skor Kartı HTML
    scorecard_html = f"""
    <div class="pd-grid" style="{grid_style}">
        <div class="pd-panel" style="{panel_style}">
            <div style="font-size: 2rem; font-weight: 700; color: var(--pd-color-accent);">
                {p_count}
            </div>
            <div class="pd-text-muted" style="font-size: 0.85rem;">Toplam Vaat</div>
        </div>
        <div class="pd-panel" style="{panel_style}">
            <div style="font-size: 2rem; font-weight: 700; color: var(--pd-color-strong);">
                {fulfilled_count}
            </div>
            <div class="pd-text-muted" style="font-size: 0.85rem;">Gerçekleşen / İcraat</div>
        </div>
        <div class="pd-panel" style="{panel_style}">
            <div style="font-size: 2rem; font-weight: 700; color: var(--pd-color-contra);">
                {contra_count}
            </div>
            <div class="pd-text-muted" style="font-size: 0.85rem;">Çelişen / Gerçekleşmeyen</div>
        </div>
        <div class="pd-panel" style="{panel_style}">
            <div style="font-size: 2rem; font-weight: 700; color: var(--pd-color-single);">
                {pending_count}
            </div>
            <div class="pd-text-muted" style="font-size: 0.85rem;">Takipte / Bekleyen</div>
        </div>
    </div>
    """

    # Kronolojik Zaman Tüneli
    all_entries = sorted(
        memory.promises + memory.attributions,
        key=lambda e: e.first_reported_at,
        reverse=True,
    )

    timeline_items = []
    for entry in all_entries:
        is_promise = entry.claim_type == "promise"
        badge_class = "pd-badge--accent" if is_promise else "pd-badge--neutral"
        type_label = "Siyasi Vaat" if is_promise else "Siyasi Beyan"

        status_badge = (
            f'<span class="pd-badge pd-badge--outline">{esc(entry.evidence_status)}</span>'
        )
        rel_label = ""
        if entry.relation_to_current:
            rel_label = (
                f'<span class="pd-badge pd-badge--neutral" style="margin-left: 0.5rem;">'
                f'{esc(entry.relation_to_current)}</span>'
            )

        date_str = esc(entry.first_reported_at[:10]) if entry.first_reported_at else "Tarihsiz"
        encoded_title = urllib.parse.quote(entry.event_title)
        item_style = "display: flex; gap: 1rem; margin-bottom: 1.5rem; position: relative;"
        date_col_style = (
            "min-width: 90px; font-weight: 600; font-size: 0.85rem; "
            "color: var(--pd-color-text-secondary);"
        )
        body_col_style = (
            "border-left: 2px solid var(--pd-color-border); padding-left: 1rem; flex: 1;"
        )

        header_style = "display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;"
        title_style = "font-weight: 600; font-size: 0.95rem; margin-bottom: 0.25rem;"
        quote_style = (
            "font-style: italic; color: var(--pd-color-text-secondary); font-size: 0.9rem;"
        )
        feed_link = f"/feed?q={encoded_title}"

        timeline_items.append(f"""
            <div class="timeline-item" style="{item_style}">
                <div style="{date_col_style}">{date_str}</div>
                <div style="{body_col_style}">
                    <div style="{header_style}">
                        <span class="pd-badge {badge_class}">{type_label}</span>
                        {status_badge}
                        {rel_label}
                    </div>
                    <div style="{title_style}">
                        <a href="{feed_link}" style="color: inherit; text-decoration: none;">
                            {esc(entry.event_title)}
                        </a>
                    </div>
                    <div style="{quote_style}">
                        "{esc(entry.claim_text)}"
                    </div>
                </div>
            </div>
        """)

    timeline_empty = '<div class="pd-text-muted">Kayıtlı olay veya beyan bulunmuyor.</div>'
    timeline_html = "".join(timeline_items) if timeline_items else timeline_empty

    # İlişki Ağacı HTML
    relations_html = []
    for r in memory.relation_chains:
        rel_badge = f'<span class="pd-badge pd-badge--neutral">{esc(r["relation"])}</span>'
        from_t = esc(r["from_title"])
        to_t = esc(r["to_title"])
        relations_html.append(f"""
            <li style="margin-bottom: 0.75rem; font-size: 0.9rem;">
                <strong>{from_t}</strong> &rarr; {rel_badge} &rarr; <strong>{to_t}</strong>
            </li>
        """)

    header_border = (
        "margin-bottom: 1rem; border-bottom: 1px solid var(--pd-color-border); "
        "padding-bottom: 0.5rem;"
    )
    r_empty = '<li class="pd-text-muted">Kayıtlı olay ilişkisi bulunmuyor.</li>'
    r_list = "".join(relations_html) if relations_html else r_empty

    content = f"""
    <div class="pd-stack pd-stack--lg">
        {head}
        {disclaimer_html}
        {scorecard_html}

        <div class="pd-grid" style="display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem;">
            <div class="pd-panel">
                <h3 style="{header_border}">Kronolojik Zaman Tüneli</h3>
                <div class="timeline-container" style="margin-top: 1rem;">
                    {timeline_html}
                </div>
            </div>

            <div class="pd-panel">
                <h3 style="{header_border}">İlişki ve Duruş Ağı ({r_count})</h3>
                <ul style="padding-left: 1.25rem;">{r_list}</ul>
            </div>
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
