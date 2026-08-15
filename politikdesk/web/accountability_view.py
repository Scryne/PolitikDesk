"""Hesap Sor (Accountability Digest) Ekranı (Spec v3.4 §8.3, §14.1).

Siyasi aktörlerin geçmiş beyanları ve vaatleri ile güncel Meclis oylamaları,
bütçe harcamaları ve Sayıştay denetim bulgularını karşılaştıran
editoryal hesap verebilirlik analiz masası.
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

EPISTEMIC_BADGES: dict[str, tuple[str, str]] = {
    "verified": ("Doğrulanmış Atıf", "pd-badge--success"),
    "supported": ("Kanıtla Desteklenen", "pd-badge--neutral"),
    "inferred": ("Olası İlişki", "pd-badge--outline"),
    "unresolved": ("Belirsiz", "pd-badge--muted"),
}


@router.get("/accountability", response_class=HTMLResponse)
def accountability_page() -> HTMLResponse:
    """Hesap Sor ana ekranı."""
    user_id = current_user_id()
    touch_last_seen(user_id)

    digest = mem_service.get_accountability_digest()

    head = page_head(
        "Hesap Sor: Editoryal Hesap Verebilirlik",
        lede=(
            "Geçmiş vaatler, TBMM oylama tutanakları ve "
            "Sayıştay kamu zararı bulguları arasındaki çapraz eşleme."
        ),
    )

    disclaimer_style = (
        "background: var(--pd-color-bg-subtle); "
        "border-left: 4px solid var(--pd-color-accent); "
        "padding: 0.85rem 1.25rem; margin-bottom: 1.5rem; "
        "font-size: 0.85rem; color: var(--pd-color-text-secondary);"
    )
    disclaimer_html = f"""
    <div class="pd-panel" style="{disclaimer_style}">
        <strong>Epistemik & Hukuki Çekince:</strong> {esc(LEGAL_DISCLAIMER)}
    </div>
    """

    cards = []
    if not digest:
        cards.append("""
            <div class="pd-panel" style="padding: 2rem; text-align: center;">
                <p class="pd-text-muted">
                    Henüz hesap verebilirlik analizi için çelişen veya tamamlanan kayıt bulunmuyor.
                </p>
            </div>
        """)
    else:
        for item in digest:
            status_key = item.get("status", "inferred")
            badge_label, badge_class = EPISTEMIC_BADGES.get(
                status_key, (status_key, "pd-badge--neutral")
            )
            conf_pct = int(item.get("confidence", 1.0) * 100)
            payload = item.get("evidence_payload") or {}
            breakdown = payload.get("score_breakdown") or {}
            target_inst_or_actor = (
                payload.get("target_institution")
                or payload.get("target_actor")
                or "Genel"
            )

            details_style = (
                "margin-top: 0.75rem; background: var(--pd-color-bg-subtle); "
                "padding: 0.75rem; border-radius: 4px; font-size: 0.85rem;"
            )
            grid_style = (
                "margin-top: 0.5rem; display: grid; "
                "grid-template-columns: 1fr 1fr; gap: 0.5rem; font-size: 0.8rem;"
            )
            target_title_esc = esc(payload.get('target_title', 'Belirtilmedi'))

            drawer_html = f"""
            <details style="{details_style}">
                <summary style="cursor: pointer; font-weight: 500; color: var(--pd-color-accent);">
                    Kanıt ve Deterministik İlişki Detayları (Güven: %{conf_pct})
                </summary>
                <div style="{grid_style}">
                    <div><strong>Hedef Olay:</strong> {target_title_esc}</div>
                    <div><strong>Hedef Kurum/Aktör:</strong> {esc(target_inst_or_actor)}</div>
                    <div><strong>Kurum:</strong> {breakdown.get('institution_score', '-')}</div>
                    <div><strong>Konu:</strong> {breakdown.get('topic_score', '-')}</div>
                    <div><strong>Zaman:</strong> {breakdown.get('temporal_score', '-')}</div>
                    <div><strong>Varlık:</strong> {breakdown.get('entity_score', '-')}</div>
                </div>

            </details>
            """

            card_panel_style = (
                "border-left: 4px solid var(--pd-color-accent); padding: 1.25rem;"
            )
            reported_date = esc(item['reported_at'][:10])
            speaker_esc = esc(item['speaker'])
            event_title_esc = esc(item['event_title'])
            promise_text_esc = esc(item['promise_text'])
            rel_str = esc(item.get('relation', 'fulfils'))
            ev_str = esc(item['evidence_status'])
            badge_label_esc = esc(badge_label)
            cards.append(f"""
                <div class="pd-panel pd-stack" style="{card_panel_style}">
                    <div style="display: flex; justify-content: space-between;">
                        <div>
                            <span class="pd-badge pd-badge--neutral">{speaker_esc}</span>
                            <span class="pd-badge {badge_class}" style="margin-left: 0.5rem;">
                                {badge_label_esc}
                            </span>
                            <span class="pd-badge pd-badge--outline" style="margin-left: 0.5rem;">
                                {reported_date}
                            </span>
                        </div>
                        <a href="/memory/{speaker_esc}" class="pd-btn pd-btn--sm">Aktör Profili</a>
                    </div>
                    <h3 style="margin-top: 0.5rem; font-size: 1.1rem;">{event_title_esc}</h3>
                    <p style="font-style: italic; color: var(--pd-color-text-secondary);">
                        "{promise_text_esc}"
                    </p>
                    <div style="font-size: 0.85rem; color: var(--pd-color-muted);">
                        İlişki Türü: <strong>{rel_str}</strong> · Kanıt: <strong>{ev_str}</strong>
                    </div>
                    {drawer_html}
                </div>
            """)




    content = f"""
    <div class="pd-stack pd-stack--lg">
        {head}
        {disclaimer_html}

        <div class="pd-stack">
            {''.join(cards)}
        </div>
    </div>
    """

    html = page(
        "Hesap Sor",
        content,
        active="/accountability",
        extra_js=ACTIVITY_JS,
    )
    return HTMLResponse(html)
