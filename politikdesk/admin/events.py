"""Olay denetimi: kuyruk, merge/split, geri alma (F2-04, F2-05).

F2-04 DoD: Belirsiz atamalar kuyrukta görünüyor; onayla/reddet/taşı
aksiyonları var.
F2-05 DoD: İki olay birleştirilebiliyor, bir olay bölünebiliyor; her
işlem `audit_log`'da; geri alınabiliyor.

`admin/router.py`'den ayrı bir dosyada tutulur: kaynak/makale ekranları
Faz 1'e, bu ekran Faz 2'ye aittir ve ikisi bağımsız değişir.
"""

from __future__ import annotations

import html
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from politikdesk.clustering.merger import (
    MergeError,
    merge_events,
    resolve_review,
    review_queue,
    split_event,
    undo_merge,
    undo_split,
)
from politikdesk.db import connection
from politikdesk.observability import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin", "events"])


class ReviewDecision(BaseModel):
    decision: str = Field(pattern="^(verified|rejected)$")


class MergeRequest(BaseModel):
    source_event_id: int
    target_event_id: int


class SplitRequest(BaseModel):
    article_ids: list[int] = Field(min_length=1)


def _guard(fn: Any, *args: Any) -> Any:
    """`MergeError`'ı 400'e çevirir — kural ihlali sunucu hatası değildir."""
    try:
        return fn(*args)
    except MergeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------- olaylar
@router.get("/events")
def list_events(
    review_flag: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
) -> list[dict[str, Any]]:
    """Olay listesi. Birleştirilmiş olaylar gizlenir."""
    conditions = ["e.merged_into_id IS NULL"]
    params: list[Any] = []
    if review_flag:
        conditions.append("e.review_flag = %s")
        params.append(review_flag)

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT e.id, e.title, e.article_count, e.independent_count,
                   e.salience_score, e.review_flag, e.first_reported_at,
                   e.last_update_at
            FROM events e
            WHERE {" AND ".join(conditions)}
            ORDER BY e.last_update_at DESC
            LIMIT %s
            """,  # noqa: S608 — koşullar sabit parçalardan kuruluyor
            [*params, limit],
        )
        return [dict(r) for r in cur.fetchall()]


@router.get("/events/{event_id}")
def event_detail(event_id: int) -> dict[str, Any]:
    """Olayın makaleleri, varlıkları ve denetim geçmişi."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM events WHERE id = %s", (event_id,))
        event = cur.fetchone()
        if event is None:
            raise HTTPException(status_code=404, detail=f"Olay yok: {event_id}")

        cur.execute(
            """
            SELECT a.id, a.title, a.canonical_url, a.cluster_score,
                   a.published_at, s.slug AS source_slug, s.tier, s.kind
            FROM articles a JOIN sources s ON s.id = a.source_id
            WHERE a.event_id = %s ORDER BY a.published_at, a.id
            """,
            (event_id,),
        )
        articles = [dict(r) for r in cur.fetchall()]

        cur.execute(
            """
            SELECT e.canonical_name, e.entity_type, e.is_key_entity
            FROM event_entities ee JOIN entities e ON e.id = ee.entity_id
            WHERE ee.event_id = %s ORDER BY e.is_key_entity DESC, e.canonical_name
            """,
            (event_id,),
        )
        entities = [dict(r) for r in cur.fetchall()]

        cur.execute(
            """
            SELECT actor, action, payload, created_at FROM audit_log
            WHERE target = %s ORDER BY id DESC LIMIT 20
            """,
            (f"events/{event_id}",),
        )
        history = [dict(r) for r in cur.fetchall()]

    payload = dict(event)
    payload.pop("centroid_embedding", None)  # 1024 sayı JSON'a basılmaz
    return {
        "event": payload, "articles": articles,
        "entities": entities, "history": history,
    }


# --------------------------------------------------------- denetim kuyruğu
@router.get("/review")
def review_list(limit: int = Query(default=50, le=200)) -> list[dict[str, Any]]:
    return [dict(r) for r in review_queue(limit)]


@router.post("/review/{event_id}")
def review_resolve(event_id: int, payload: ReviewDecision) -> dict[str, Any]:
    return _guard(resolve_review, event_id, payload.decision)


# ------------------------------------------------------------ merge / split
@router.post("/events/merge")
def merge(payload: MergeRequest) -> dict[str, Any]:
    result = _guard(merge_events, payload.source_event_id, payload.target_event_id)
    return result.as_dict()


@router.post("/events/{event_id}/undo-merge")
def undo_merge_endpoint(event_id: int) -> dict[str, Any]:
    return _guard(undo_merge, event_id).as_dict()


@router.post("/events/{event_id}/split")
def split(event_id: int, payload: SplitRequest) -> dict[str, Any]:
    return _guard(split_event, event_id, payload.article_ids).as_dict()


@router.post("/events/{event_id}/undo-split")
def undo_split_endpoint(event_id: int) -> dict[str, Any]:
    return _guard(undo_split, event_id).as_dict()


# ------------------------------------------------------------------- HTML
_STYLE = """
 body { font-family: system-ui, sans-serif; margin: 2rem; max-width: 1100px;
        color: #1f2328; }
 h1 { font-size: 1.4rem; }
 table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
 th, td { border-bottom: 1px solid #d0d7de; padding: .5rem; text-align: left;
          font-size: .9rem; vertical-align: top; }
 th { background: #f6f8fa; }
 small { color: #656d76; }
 button { cursor: pointer; padding: .2rem .6rem; }
 .warn { color: #cf222e; }
"""

_SCRIPT = """
async function decide(id, decision) {
  const r = await fetch('/admin/review/' + id, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({decision: decision})
  });
  if (r.ok) { location.reload(); } else { alert(await r.text()); }
}
async function doMerge() {
  const src = document.getElementById('src').value;
  const tgt = document.getElementById('tgt').value;
  const r = await fetch('/admin/events/merge', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({source_event_id: +src, target_event_id: +tgt})
  });
  if (r.ok) { location.reload(); } else { alert(await r.text()); }
}
"""


def _reason_of(row: dict[str, Any]) -> str:
    payload = row.get("flag_payload") or {}
    return str(payload.get("reason", "—"))


def _conflicts_of(row: dict[str, Any]) -> str:
    payload = row.get("flag_payload") or {}
    return ", ".join(payload.get("numeric_conflicts", [])) or "—"


@router.get("/review/", response_class=HTMLResponse)
def review_dashboard() -> str:
    """Denetim kuyruğu ekranı (F2-04 görsel karşılığı)."""
    queue = review_queue(100)

    if not queue:
        body = "<p>Denetim bekleyen olay yok.</p>"
    else:
        rows = "".join(
            "<tr>"
            f"<td><a href='/admin/events/{r['id']}'>{r['id']}</a></td>"
            f"<td>{html.escape((r['title'] or '')[:90])}</td>"
            f"<td>{r['article_count']}</td>"
            f"<td><small>{html.escape(_reason_of(r))}</small></td>"
            f"<td><small class='warn'>{html.escape(_conflicts_of(r))}</small></td>"
            f"<td><button onclick=\"decide({r['id']},'verified')\">onayla</button>"
            f" <button onclick=\"decide({r['id']},'rejected')\">reddet</button></td>"
            "</tr>"
            for r in queue
        )
        body = (
            "<table><tr><th>#</th><th>Başlık</th><th>Makale</th><th>Sebep</th>"
            "<th>Sayısal çelişki</th><th>Karar</th></tr>"
            f"{rows}</table>"
        )

    return (
        "<!doctype html><html lang='tr'><head><meta charset='utf-8'>"
        "<title>PolitikDesk — Denetim Kuyruğu</title>"
        f"<style>{_STYLE}</style></head><body>"
        f"<h1>Denetim Kuyruğu <small>({len(queue)} olay)</small></h1>"
        "<p><small>Kümeleme kararı belirsiz kalan, varlık kısıtı doğrulanamayan "
        "veya sayısal çelişki içeren olaylar. Onaylamak atamayı kalıcı kılar.</small></p>"
        f"{body}"
        "<h2>Olay birleştir</h2>"
        "<p><small>Kaynak olay hedefe taşınır; kaynak silinmez, "
        "<code>merged_into_id</code> ile işaretlenir ve geri alınabilir.</small></p>"
        "<p>kaynak <input id='src' size='6'> → hedef <input id='tgt' size='6'> "
        "<button onclick='doMerge()'>birleştir</button></p>"
        "<p><a href='/admin/'>← panoya dön</a></p>"
        f"<script>{_SCRIPT}</script></body></html>"
    )
