"""Vaat Takibi (Promise Tracker) Ekranı (Spec v3.4 §7.3, §14.1).

Siyasi aktörlerin, liderlerin ve hükümet sözcülerinin verdikleri
vaatleri, kanunlaşma / gerçekleşme durumlarını ve resmi kaynak
teyitlerini tablo/kart görünümünde listeler.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from politikdesk.political_memory import service as mem_service
from politikdesk.political_memory.accountability import LEGAL_DISCLAIMER
from politikdesk.users import current_user_id, touch_last_seen
from politikdesk.web.ui import (
    ACTIVITY_JS,
    esc,
    page,
    page_head,
)

router = APIRouter(tags=["web"])


def _status_badge(outcome: str, evidence_status: str) -> str:
    if outcome == "fulfils":
        return '<span class="pd-badge pd-badge--strong">Gerçekleşti (Kanunlaştı)</span>'
    if outcome == "fails":
        return '<span class="pd-badge pd-badge--contra">Gerçekleşmedi / Reddedildi</span>'
    if outcome == "contradicts":
        return '<span class="pd-badge pd-badge--contra">Çelişki Tespit Edildi</span>'
    return '<span class="pd-badge pd-badge--partial">Takipte / Süreç Devam Ediyor</span>'


@router.get("/promises", response_class=HTMLResponse)
@router.get("/vaatler", response_class=HTMLResponse)
def promises_page() -> HTMLResponse:
    """Vaat Takibi ana ekranı."""
    user_id = current_user_id()
    touch_last_seen(user_id)

    promises = mem_service.get_promise_tracker()

    head = page_head(
        "Vaat Takip Masası",
        lede=(
            "Siyasi aktörlerin kamuoyuna verdikleri taahhütlerin ve "
            "yasama adımlarının doğrulanmış kaydı."
        ),
    )

    rows_html = []
    if not promises:
        empty_msg = (
            "Henüz kayıtlı siyasi vaat bulunmuyor. "
            "Siyaset dikeyinden veri çekildikçe burası otomatik dolacaktır."
        )
        rows_html.append(f"""
            <tr>
                <td colspan="5" class="pd-table__empty" style="text-align:center; padding: 2rem;">
                    {empty_msg}
                </td>
            </tr>
        """)
    else:
        for p in promises:
            badge = _status_badge(p["outcome_relation"], p["evidence_status"])
            link_style = (
                "color: var(--pd-color-accent); text-decoration: none; font-weight: 500;"
            )
            reported_date = esc(p['first_reported_at'][:10])
            speaker_esc = esc(p['speaker'])
            title_esc = esc(p['event_title'])
            claim_esc = esc(p['claim_text'])
            claim_div_style = (
                "font-size: 0.85rem; color: var(--pd-color-muted); margin-top: 0.25rem;"
            )
            rows_html.append(f"""
                <tr>
                    <td style="font-weight: 500;">{speaker_esc}</td>
                    <td>
                        <a href="/events/{p['event_id']}" style="{link_style}">
                            {title_esc}
                        </a>
                        <div style="{claim_div_style}">
                            "{claim_esc}"
                        </div>
                    </td>
                    <td>{badge}</td>
                    <td style="font-size: 0.85rem; color: var(--pd-color-muted);">
                        {reported_date}
                    </td>
                    <td>
                        <a
                            href="/memory/{speaker_esc}"
                            class="pd-btn pd-btn--sm"
                            style="font-size: 0.75rem;"
                        >
                            Hafıza
                        </a>
                    </td>
                </tr>

            """)



    disc_style = (
        "background: var(--pd-color-bg-subtle); "
        "border-left: 4px solid var(--pd-color-accent); "
        "padding: 0.85rem 1.25rem; font-size: 0.85rem; "
        "color: var(--pd-color-text-secondary);"
    )
    disclaimer_html = f"""
    <div class="pd-panel" style="{disc_style}">
        <strong>Epistemik & Hukuki Çekince:</strong> {esc(LEGAL_DISCLAIMER)}
    </div>
    """


    content = f"""
    <div class="pd-stack pd-stack--lg">
        {head}
        {disclaimer_html}

        <div class="pd-panel">
            <table class="pd-table" style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="border-bottom: 1px solid var(--pd-color-border); text-align: left;">
                        <th style="padding: 0.75rem;">Aktör</th>
                        <th style="padding: 0.75rem;">Vaat / Taahhüt</th>
                        <th style="padding: 0.75rem;">Durum</th>
                        <th style="padding: 0.75rem;">Tarih</th>
                        <th style="padding: 0.75rem;">İşlem</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows_html)}
                </tbody>
            </table>
        </div>
    </div>
    """

    html = page(
        "Vaat Takibi",
        content,
        active="/promises",
        extra_js=ACTIVITY_JS,
    )
    return HTMLResponse(html)
