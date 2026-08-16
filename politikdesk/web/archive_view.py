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
    esc,
    page,
    page_head,
)

router = APIRouter(tags=["web"])


@router.get("/archive", response_class=HTMLResponse)
@router.get("/arsiv", response_class=HTMLResponse)
def archive_page() -> HTMLResponse:
    """Yayın Arşivi ana ekranı."""
    user_id = current_user_id()
    touch_last_seen(user_id)

    records = list_archived_publications(limit=50)

    head = page_head(
        "Editoryal Yayın ve Kanıt Arşivi",
        lede=(
            "Yayınlanan her metnin zaman damgası, model sürümü ve "
            "dayandığı birincil kanıt kütüğü (Spec §14.4)."
        ),
    )

    cards = []
    if not records:
        cards.append("""
            <div class="pd-panel" style="padding: 2rem; text-align: center;">
                <p class="pd-text-muted">
                    Arşivde henüz yayınlanmış veya kabul edilmiş taslak bulunmuyor.
                </p>
            </div>
        """)
    else:
        for r in records:
            grounded_badge = (
                '<span class="pd-badge pd-badge--strong">Doğrulanmış</span>'
                if r["is_grounded"]
                else '<span class="pd-badge pd-badge--contra">Grounding Engelli</span>'
            )
            created_str = esc(r["created_at"][:19].replace("T", " "))
            body_style = (
                "background: var(--pd-color-surface-subtle); padding: 1rem; "
                "border-radius: 4px; font-family: monospace; font-size: 0.9rem; "
                "white-space: pre-wrap;"
            )
            h4_style = "margin: 0.5rem 0; font-size: 1rem; color: var(--pd-color-text-secondary);"
            angle_esc = esc(r["angle"].upper())
            title_esc = esc(r["event_title"])
            body_esc = esc(r["body"])
            action_esc = esc(r["user_action"] or "üretildi")
            cited_len = len(r["cited_claim_ids"])
            cards.append(f"""
                <div class="pd-panel pd-stack" style="padding: 1.25rem; margin-bottom: 1rem;">
                    <div style="display: flex; justify-content: space-between;">
                        <div>

                            <span class="pd-badge pd-badge--neutral">Açı: {angle_esc}</span>
                            <span class="pd-badge pd-badge--outline" style="margin-left: 0.5rem;">
                                {created_str}
                            </span>
                            <span style="margin-left: 0.5rem;">{grounded_badge}</span>
                        </div>
                        <a href="/events/{r["event_id"]}" class="pd-btn pd-btn--sm">Olay Detayı</a>
                    </div>
                    <h4 style="{h4_style}">{title_esc}</h4>
                    <div style="{body_style}">{body_esc}</div>
                    <div style="font-size: 0.8rem; color: var(--pd-color-muted);">
                        Dayanak: {cited_len} iddia · Aksiyon: <strong>{action_esc}</strong>
                    </div>
                </div>
            """)

    content = f"""
    <div class="pd-stack pd-stack--lg">
        {head}

        <div class="pd-stack">
            {"".join(cards)}
        </div>
    </div>
    """

    html = page(
        "Yayın Arşivi",
        content,
        active="/archive",
        extra_js=ACTIVITY_JS,
    )
    return HTMLResponse(html)
