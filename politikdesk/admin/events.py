"""Olay denetimi: kuyruk, merge/split, geri alma (F2-04, F2-05).

F2-04 DoD: Belirsiz atamalar kuyrukta görünüyor; onayla/reddet/taşı
aksiyonları var.
F2-05 DoD: İki olay birleştirilebiliyor, bir olay bölünebiliyor; her
işlem `audit_log`'da; geri alınabiliyor.

`admin/router.py`'den ayrı bir dosyada tutulur: kaynak/makale ekranları
Faz 1'e, bu ekran Faz 2'ye aittir ve ikisi bağımsız değişir.
"""

from __future__ import annotations

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
        "event": payload,
        "articles": articles,
        "entities": entities,
        "history": history,
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
_SCRIPT = """
async function pdDecide(id, decision, btn) {
  // Buton genişliği değişmez (Bölüm 8.5): metin yerinde kalır, yalnızca
  // devre dışı olur. Aynı karara iki kez basılmasını da bu engelliyor.
  var row = btn.closest('tr');
  row.querySelectorAll('button').forEach(function(b){ b.disabled = true; });
  try {
    var r = await fetch('/admin/review/' + id, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({decision: decision})
    });
    if (!r.ok) throw new Error(await r.text());
    location.reload();
  } catch (e) {
    row.querySelectorAll('button').forEach(function(b){ b.disabled = false; });
    window.pdToast('Karar kaydedilemedi: ' + e.message);
  }
}

async function pdMerge() {
  var src = document.getElementById('src').value;
  var tgt = document.getElementById('tgt').value;
  var note = document.getElementById('merge-status');
  if (!src || !tgt) {
    note.textContent = 'İki olay kimliği de gerekli.';
    return;
  }
  note.textContent = 'Birleştiriliyor…';
  try {
    var r = await fetch('/admin/events/merge', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({source_event_id: +src, target_event_id: +tgt})
    });
    if (!r.ok) {
      var body = await r.json().catch(function(){ return null; });
      throw new Error(body && body.detail ? body.detail : 'Birleştirilemedi.');
    }
    location.reload();
  } catch (e) {
    note.textContent = e.message;
  }
}
window.pdAction('decide', pdDecide);
window.pdAction('merge', pdMerge);
"""

# Kuyruğa düşme sebepleri — ham anahtar yerine ne olduğunu söyleyen cümle.
# "numeric_conflict" bir sistem dilidir (Ek B.2); kullanıcı "faiz %40 mı
# %42 mi" sorusuna bakıyor.
_REASON_LABELS = {
    "low_confidence": "Kümeleme skoru eşiğe yakın",
    "numeric_conflict": "Aynı göstergede farklı sayı",
    "entity_mismatch": "Anahtar varlık doğrulanamadı",
    "user_flag": "Kullanıcı işaretledi",
}


def _reason_of(row: dict[str, Any]) -> str:
    payload = row.get("flag_payload") or {}
    raw = str(payload.get("reason", ""))
    return _REASON_LABELS.get(raw, raw or "—")


def _conflicts_of(row: dict[str, Any]) -> str:
    payload = row.get("flag_payload") or {}
    return ", ".join(payload.get("numeric_conflicts", []))


@router.get("/review/", response_class=HTMLResponse)
def review_dashboard() -> str:
    """Denetim kuyruğu ekranı (F2-04 görsel karşılığı).

    Bu sayfanın tek işi (BRIEF): *"Hangi kümeleme kararı benim onayımı
    bekliyor?"* — bu yüzden kuyruk ekranın tamamıdır ve merge aracı
    altta, ayrı bir kartta durur. Merge günde bir kez kullanılan bir
    araçtır; kuyruk her ziyaretin sebebidir.
    """
    from politikdesk.web.ui import (
        button,
        card,
        cell,
        empty_state,
        esc,
        notice,
        page,
        page_head,
        table,
    )
    from politikdesk.web.ui import (
        format as fmt,
    )

    try:
        queue = review_queue(100)
    except Exception as exc:  # noqa: BLE001
        log.warning("review_dashboard_db_unavailable", error=str(exc))
        from politikdesk.web.ui import error_state, page

        return page(
            "Denetim kuyruğu",
            error_state(
                "Veritabanı bağlantısı yok",
                "Denetim kuyruğu çalışan bir PostgreSQL veritabanı gerektirir (`pd start`).",
            ),
            active="/admin/",
            crumbs=(("Denetim", None), ("Kuyruk", None)),
        )

    rows = []
    for r in queue:
        conflict = _conflicts_of(r)
        rows.append(
            "<tr>"
            + cell(
                f'<a class="mono" href="/event/{r["id"]}">#{r["id"]}</a>',
                label="Olay",
            )
            + cell(
                f'<a class="plain" href="/event/{r["id"]}">{esc((r["title"] or "")[:110])}</a>',
                label="Başlık",
            )
            + cell(esc(fmt.number(r["article_count"])), label="Makale", cls="num")
            + cell(f'<span class="subtle">{esc(_reason_of(r))}</span>', label="Sebep")
            + cell(
                f'<span class="badge contra">{esc(conflict)}</span>'
                if conflict
                else '<span class="subtle">—</span>',
                label="Sayısal çelişki",
            )
            + cell(
                '<div class="btn-row">'
                + button(
                    "Onayla",
                    small=True,
                    icon_name="check",
                    action="decide",
                    action_args=(r["id"], "verified"),
                )
                + button(
                    "Reddet",
                    small=True,
                    icon_name="close",
                    action="decide",
                    action_args=(r["id"], "rejected"),
                )
                + "</div>",
                label="Karar",
            )
            + "</tr>"
        )

    if queue:
        queue_card = card(
            table(
                (
                    ("Olay", ""),
                    ("Başlık", ""),
                    ("Makale", "num"),
                    ("Sebep", ""),
                    ("Sayısal çelişki", ""),
                    ("Karar", ""),
                ),
                rows,
            ),
            title=f"Bekleyen karar · {len(queue)}",
            actions='<span class="subtle" style="font-size:var(--text-xs)">'
            "onaylamak atamayı kalıcı kılar</span>",
        )
    else:
        # Boş durum (10.1) — burada boş olmak İYİ bir haberdir; metin de
        # öyle söylemeli, bir eksiklik gibi değil.
        queue_card = card(
            empty_state(
                "Bekleyen karar yok",
                "Kümeleme kararlarının hepsi net. Bir olay belirsiz kalırsa, "
                "sayısal çelişki içerirse veya sen “bu yanlış” dersen burada "
                "görünür.",
                action=button("Gündeme dön", href="/feed", variant="primary"),
                icon_name="check",
            )
        )

    merge_card = card(
        notice(
            "<p>Kaynak olay hedefe taşınır. <b>Kaynak silinmez</b> — "
            "<span class='mono'>merged_into_id</span> ile işaretlenir ve işlem "
            "%100 geri alınabilir (<span class='mono'>/admin/events/"
            "{id}/undo-merge</span>).</p>"
        )
        + '<div class="row" style="margin-top:var(--space-4);'
        'align-items:flex-end">' + '<div class="field" style="max-width:120px">'
        '<label for="src">Kaynak olay</label>'
        '<input type="number" id="src" placeholder="örn. 412"></div>'
        + '<span class="subtle" style="padding-bottom:10px">→</span>'
        + '<div class="field" style="max-width:120px">'
        '<label for="tgt">Hedef olay</label>'
        '<input type="number" id="tgt" placeholder="örn. 398"></div>'
        + button("Birleştir", variant="primary", icon_name="review", action="merge")
        + '<span id="merge-status" class="subtle" aria-live="polite" '
        'style="font-size:var(--text-xs);padding-bottom:10px"></span>' + "</div>",
        title="Olay birleştir",
    )

    body = f"""
{
        page_head(
            "Denetim kuyruğu",
            lede="Kümeleme kararı belirsiz kalan, varlık kısıtı doğrulanamayan veya "
            "sayısal çelişki içeren olaylar.",
            actions=button("Boru hattı", href="/admin/", icon_name="pipeline"),
        )
    }
<div class="stack">{queue_card}{merge_card}</div>
"""
    return page(
        "Denetim kuyruğu",
        body,
        active="/admin/review/",
        crumbs=(("Denetim", None), ("Denetim kuyruğu", None)),
        extra_js=_SCRIPT,
    )
