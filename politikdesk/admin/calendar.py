"""Beklenen gelişmeler takvimi — admin ekranı (F2-18).

DoD: TÜİK veri takvimi ve TCMB PPK tarihleri (12 ay) girilmiş.

Takvim **elle** girilir ve bu bilinçlidir: TÜİK'in veri yayımlama takvimi
JS ile yüklenen bir sayfada durur (F1-03'te çözülemedi) ve yılda bir kez
değişir. 12 aylık bir listeyi elle girmek, kırılgan bir kazıyıcı
sürdürmekten ucuzdur. Otomatik besleme, akış bulunduğunda gelir (B-42).
"""

from __future__ import annotations

import html
from datetime import datetime
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


def _linked_cell(row: dict[str, Any]) -> str:
    event_id = row.get("linked_event_id")
    if not event_id:
        return "—"
    title = html.escape((row.get("linked_event_title") or "")[:50])
    return f"<a href='/admin/events/{event_id}'>{title}</a>"


@router.get("/calendar/", response_class=HTMLResponse)
def calendar_dashboard() -> str:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(r['expected_at'])[:16])}</td>"
        f"<td>{html.escape(r['title'][:80])}</td>"
        f"<td>{html.escape(r['source_slug'] or '—')}</td>"
        f"<td>{html.escape(r['status'])}</td>"
        f"<td>{_linked_cell(r)}</td>"
        "</tr>"
        for r in list_scheduled(limit=200)
    )
    return (
        "<!doctype html><html lang='tr'><head><meta charset='utf-8'>"
        "<title>PolitikDesk — Beklenen Gelişmeler</title><style>"
        "body{font-family:system-ui,sans-serif;margin:2rem;max-width:1000px}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{border-bottom:1px solid #d0d7de;padding:.5rem;text-align:left;font-size:.9rem}"
        "th{background:#f6f8fa}small{color:#656d76}"
        "</style></head><body>"
        "<h1>Beklenen Gelişmeler</h1>"
        "<p><small>Spec §9.5: ürün yalnızca olanı değil, olacağı da bilir. "
        "Gerçekleşen olay otomatik bağlanır (F2-19).</small></p>"
        "<table><tr><th>Beklenen zaman</th><th>Başlık</th><th>Kaynak</th>"
        f"<th>Durum</th><th>Bağlanan olay</th></tr>{rows}</table>"
        "<p><a href='/admin/'>← panoya dön</a></p>"
        "</body></html>"
    )
