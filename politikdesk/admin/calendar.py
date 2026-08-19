"""Beklenen gelişmeler takvimi — admin ekranı (F2-18).

DoD: TÜİK veri takvimi ve TCMB PPK tarihleri (12 ay) girilmiş.

Takvim **elle** girilir ve bu bilinçlidir: TÜİK'in veri yayımlama takvimi
JS ile yüklenen bir sayfada durur (F1-03'te çözülemedi) ve yılda bir kez
değişir. 12 aylık bir listeyi elle girmek, kırılgan bir kazıyıcı
sürdürmekten ucuzdur. Otomatik besleme, akış bulunduğunda gelir (B-42).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from politikdesk.context.scheduler_match import (
    add_scheduled,
    list_scheduled,
    match_pending,
)
from politikdesk.observability import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin", "calendar"])


class ScheduledEventIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    expected_at: datetime
    source_slug: str | None = None
    vertical: str = "macro_economy"


@router.get("/calendar")
def calendar_list(upcoming_only: bool = False) -> list[dict[str, Any]]:
    return list_scheduled(upcoming_only=upcoming_only)


@router.post("/calendar")
def calendar_add(payload: ScheduledEventIn) -> dict[str, int]:
    try:
        scheduled_id = add_scheduled(
            title=payload.title,
            expected_at=payload.expected_at,
            source_slug=payload.source_slug,
            vertical=payload.vertical,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": scheduled_id}


@router.post("/calendar/match")
def calendar_match() -> dict[str, int]:
    """Beklenen gelişmeleri gerçekleşen olaylarla eşleştir (F2-19)."""
    return match_pending()


# Durum -> (token, etiket). Ham anahtar gösterilmez (Ek B.2 sistem dili).
_STATUS = {
    "pending": ("neutral", "bekliyor"),
    "matched": ("strong", "gerçekleşti"),
    "missed": ("single", "kaçırıldı"),
    "cancelled": ("unverified", "iptal"),
}


@router.get("/calendar/", response_class=HTMLResponse)
def calendar_dashboard() -> str:
    """Beklenen gelişmeler ekranı (F2-18/F2-19).

    Bu sayfanın tek işi (BRIEF): *"Sırada ne var ve gerçekleşen olayla
    eşleşti mi?"* — bu yüzden **bekleyenler üstte** durur ve geçmiş
    kayıtlar altta. Tabloyu tarihe göre tek blokta dizmek, kullanıcıyı
    "bugün nerede" diye aramaya zorlardı.
    """
    from datetime import datetime

    from politikdesk.web.ui import (
        button,
        card,
        cell,
        empty_state,
        esc,
        kpi,
        page,
        page_head,
        relative_time,
        table,
    )
    from politikdesk.web.ui import (
        format as fmt,
    )

    items = list_scheduled(limit=200)
    now = datetime.now(UTC)

    def is_upcoming(row: dict[str, Any]) -> bool:
        expected = row.get("expected_at")
        if not isinstance(expected, datetime):
            return row.get("status") == "pending"
        reference = now if expected.tzinfo else now.replace(tzinfo=None)
        return expected >= reference and row.get("status") == "pending"

    upcoming = [r for r in items if is_upcoming(r)]
    past = [r for r in items if not is_upcoming(r)]
    matched = sum(1 for r in items if r.get("status") == "matched")

    def build_rows(rows: list[dict[str, Any]]) -> list[str]:
        out = []
        for r in rows:
            token, label = _STATUS.get(r["status"], ("neutral", r["status"]))
            event_id = r.get("linked_event_id")
            linked = (
                f'<a href="/event/{event_id}">{esc((r.get("linked_event_title") or "")[:50])}</a>'
                if event_id
                else '<span class="subtle">—</span>'
            )
            out.append(
                "<tr>"
                + cell(
                    f"{esc(fmt.date_time(r['expected_at']))}"
                    f'<div class="cell-sub">{relative_time(r["expected_at"])}</div>',
                    label="Beklenen zaman",
                )
                + cell(esc(r["title"][:100]), label="Başlık")
                + cell(
                    f'<span class="mono subtle">{esc(r["source_slug"] or "—")}</span>',
                    label="Kaynak",
                )
                + cell(f'<span class="badge {token}">{esc(label)}</span>', label="Durum")
                + cell(linked, label="Bağlanan olay")
                + "</tr>"
            )
        return out

    headers = (
        ("Beklenen zaman", ""),
        ("Başlık", ""),
        ("Kaynak", ""),
        ("Durum", ""),
        ("Bağlanan olay", ""),
    )

    if items:
        upcoming_card = card(
            table(headers, build_rows(upcoming))
            if upcoming
            else empty_state(
                "Sırada bekleyen yok",
                "Takvim elle girilir (TÜİK veri takvimi, TCMB PPK tarihleri). "
                "Yeni kayıt için POST /admin/calendar.",
                icon_name="calendar",
            ),
            title=f"Sırada · {len(upcoming)}",
        )
        past_card = (
            card(table(headers, build_rows(past)), title=f"Geçmiş · {len(past)}") if past else ""
        )
    else:
        upcoming_card = card(
            empty_state(
                "Takvim boş",
                "Spec §9.5: ürün yalnızca olanı değil, olacağı da bilir. TÜİK "
                "veri takvimi ve TCMB PPK tarihleri elle girilir — yılda bir "
                "kez değişen 12 aylık bir listeyi elle girmek, kırılgan bir "
                "kazıyıcı sürdürmekten ucuzdur (B-42).",
                action=button("Boru hattına dön", href="/admin/", variant="primary"),
                icon_name="calendar",
            )
        )
        past_card = ""

    body = f"""
{
        page_head(
            "Beklenen gelişmeler",
            lede="Spec §9.5: ürün yalnızca olanı değil, olacağı da bilir. "
            "Gerçekleşen olay otomatik bağlanır (F2-19).",
            actions=button("Eşleştirmeyi çalıştır", icon_name="refresh", action="match"),
        )
    }
<div class="stack">
  <div class="kpis">
    {kpi("Sırada", fmt.number(len(upcoming)), unit="kayıt", icon_name="calendar")}
    {kpi("Gerçekleşti", fmt.number(matched), unit="kayıt", icon_name="check")}
    {kpi("Toplam", fmt.number(len(items)), unit="kayıt", icon_name="briefing")}
  </div>
  {upcoming_card}
  {past_card}
</div>
"""
    js = """
async function pdMatch(){
  try {
    var r = await fetch('/admin/calendar/match', {method:'POST'});
    if (!r.ok) throw new Error(r.status);
    window.pdToast('Eşleştirme tamamlandı.');
    setTimeout(function(){ location.reload(); }, 500);
  } catch (e) {
    window.pdToast('Eşleştirme çalıştırılamadı. Veritabanına ulaşılamıyor olabilir.');
  }
}
window.pdAction('match', pdMatch);
"""
    return page(
        "Beklenen gelişmeler",
        body,
        active="/admin/calendar/",
        crumbs=(("Denetim", None), ("Beklenen gelişmeler", None)),
        extra_js=js,
    )

