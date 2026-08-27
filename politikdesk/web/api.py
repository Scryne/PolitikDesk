"""Arayüzün JSON uçları (F3-11, F3-14, F3-15, F3-19, F3-21).

Kritik uç: `POST /api/events/{id}/drafts`. F3-11 DoD'sinin ikinci yarısı
**"API doğrudan çağrılsa da reddediyor"** burada kanıtlanır — kapı bu
dosyada değil `editorial/guards.py` içinde durur; burası yalnızca
`GenerationBlocked`'ı HTTP 409'a çevirir.

⛔ Bu modülde X'e (veya başka bir platforma) giden **hiçbir giden POST
yoktur** (Spec §15 madde 6, Kapı G3 #9). `/publish` ucu yalnızca metni
ve bir Web Intent ADRESİNİ döndürür.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from politikdesk.editorial import repository as editorial_repo
from politikdesk.editorial import service
from politikdesk.editorial.generator import ANGLES
from politikdesk.editorial.guards import GenerationBlocked, GroundingBlocked
from politikdesk.editorial.profile_compiler import compile_and_store, load_profile
from politikdesk.llm.errors import BudgetExceeded, LLMError
from politikdesk.metrics import record_activity
from politikdesk.observability import get_logger
from politikdesk.users import current_user_id
from politikdesk.web import repository
from politikdesk.web.export_formats import STATUS_LABELS

log = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["api"])


# ------------------------------------------------------------------ modeller
class DraftRequest(BaseModel):
    angle: Literal["inform", "analyze", "critique", "accountability"]


class ActionRequest(BaseModel):
    action: Literal["accepted", "edited", "regenerated", "rejected"]
    final_body: str | None = Field(default=None, max_length=4000)


class FeedbackRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)
    claim_id: int | None = None


class ActivityRequest(BaseModel):
    kind: Literal["page_view", "heartbeat", "event_open", "understood"]
    path: str | None = Field(default=None, max_length=200)
    event_id: int | None = None
    duration_ms: int | None = Field(default=None, ge=0, le=24 * 3600 * 1000)


class ProfileRequest(BaseModel):
    """Editoryal Kimlik Kartı — 10 soru (Editoryal Profil).

    ⛔ Bu modele ideolojik/siyasi bir alan EKLENEMEZ. Şemada karşılığı
    yoktur ve `tests/test_editorial.py` hem modeli hem tabloyu tarar.
    """

    tone: list[str] = Field(default_factory=list)
    sentence_length: str | None = None
    formality: int | None = Field(default=None, ge=1, le=5)
    emoji_usage: str | None = None
    hashtag_usage: str | None = None
    citation_habit: str | None = None
    citation_policy: str | None = None
    topic_priorities: str | list[str] = ""
    avoid_list: str | list[str] = ""
    quote_habit: str | None = None
    uncertainty_handling: str | None = None


# ------------------------------------------------------------------- taslak
@router.get("/events/{event_id}/can-generate")
def can_generate(event_id: int) -> dict[str, Any]:
    """UI butonunun durumu — API'nin 409 kararıyla AYNI fonksiyondan."""
    return service.can_generate(event_id)


@router.post("/events/{event_id}/drafts", status_code=201)
def create_draft(event_id: int, payload: DraftRequest) -> dict[str, Any]:
    """Taslak üretir (F3-10) veya kapıya takılırsa 409 döner (F3-11)."""
    user_id = current_user_id()
    try:
        return service.generate_for_event(event_id=event_id, angle=payload.angle, user_id=user_id)
    except GenerationBlocked as blocked:
        # 409 Conflict: istek geçerli ama kaynağın DURUMU üretime izin
        # vermiyor. 403 olurdu ki bu bir yetki sorunu değil.
        log.info("draft_blocked", event_id=event_id, reason=blocked.reason)
        raise HTTPException(status_code=409, detail=blocked.as_dict()) from blocked
    except BudgetExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={"message": f"Günlük LLM bütçesi aşıldı: {exc}", "reason": "budget"},
        ) from exc
    except LLMError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": f"Model çağrısı başarısız: {type(exc).__name__}",
                "reason": "llm_error",
            },
        ) from exc


@router.get("/events/{event_id}/drafts")
def list_drafts(event_id: int) -> list[dict[str, Any]]:
    return editorial_repo.list_drafts(event_id)


@router.post("/drafts/{draft_id}/action")
def draft_action(draft_id: int, payload: ActionRequest) -> dict[str, Any]:
    """Kabul/düzenle/yeniden üret/reddet (F3-14)."""
    try:
        return service.apply_action(
            draft_id=draft_id, action=payload.action, final_body=payload.final_body
        )
    except GroundingBlocked as blocked:
        log.info("draft_action_grounding_blocked", draft_id=draft_id, action=payload.action)
        raise HTTPException(status_code=409, detail=blocked.as_dict()) from blocked
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/drafts/{draft_id}/publish")
def publish(draft_id: int) -> dict[str, Any]:
    """Yayın köprüsü verisi (F3-15). **Gönderim yapmaz.**"""
    try:
        return service.publish_payload(draft_id)
    except GroundingBlocked as blocked:
        log.info("draft_publish_grounding_blocked", draft_id=draft_id)
        raise HTTPException(status_code=409, detail=blocked.as_dict()) from blocked
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# --------------------------------------------------------------- geri bildirim
@router.post("/events/{event_id}/feedback", status_code=201)
def add_feedback(event_id: int, payload: FeedbackRequest) -> dict[str, Any]:
    """ "Bu yanlış" (F3-21) — olayı denetim kuyruğuna düşürür."""
    return repository.add_feedback(
        event_id=event_id,
        user_id=current_user_id(),
        note=payload.note,
        claim_id=payload.claim_id,
    )


# ------------------------------------------------------------------- ölçüm
@router.post("/activity", status_code=204)
async def activity(request: Request) -> None:
    """Kullanım izi (F3-19).

    `navigator.sendBeacon` gövdeyi `Blob` olarak yollar ve içerik tipi
    her tarayıcıda `application/json` olmaz; bu yüzden gövde elle
    ayrıştırılır. Hatalı gövde 4xx üretmez: ölçüm kaybı sayfayı
    bozmamalıdır.
    """
    try:
        payload = ActivityRequest.model_validate_json(await request.body())
    except Exception:  # noqa: BLE001 — bozuk beacon sessizce yutulur
        log.debug("activity_payload_invalid")
        return

    from starlette.concurrency import run_in_threadpool

    await run_in_threadpool(
        record_activity,
        user_id=current_user_id(),
        kind=payload.kind,
        event_id=payload.event_id,
        path=payload.path,
        duration_ms=payload.duration_ms,
    )


# --------------------------------------------------------------- profil (F3-08)
@router.get("/profile")
def get_profile() -> dict[str, Any]:
    profile = load_profile(current_user_id())
    return profile or {"exists": False}


@router.put("/profile")
def put_profile(payload: ProfileRequest) -> dict[str, Any]:
    try:
        return compile_and_store(current_user_id(), payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/angles")
def angles() -> list[dict[str, str]]:
    """Açı sözlüğü — buton metinleri koddan gelir (Spec §14.3 dil kararı)."""
    return [
        {"key": key, "label": label, "instruction": instruction}
        for key, (label, instruction) in ANGLES.items()
    ]


@router.get("/events/{event_id}/card.svg")
def event_card_svg_endpoint(event_id: int) -> Response:
    """Olay ve teyitli iddialar için 1200x675 SVG doğruluk infografiği döner."""
    from politikdesk.editorial.infographics import render_event_card_svg

    svg_content = render_event_card_svg(event_id)
    if not svg_content:
        raise HTTPException(status_code=404, detail="Olay veya teyitli kanıt kartı bulunamadı.")

    return Response(
        content=svg_content,
        media_type="image/svg+xml",
        headers={
            "Content-Disposition": f'inline; filename="politikdesk-event-{event_id}.svg"',
            "Cache-Control": "public, max-age=300",
        },
    )


# --------------------------------------------------------------- siyaset dikeyi
@router.get("/memory/actors")
def search_memory_actors(q: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """Siyasi hafıza aktörlerini filtreler ve sayfalar.

    Sözleşme `{actors: [{name, entity_type, …}], total, …}` (D-02). Komuta
    paleti artık bu ucu DEĞİL `/api/search`'ü çağırır; burası siyasi
    hafıza ekranının kendi ucudur ve sözleşmesi
    `tests/test_command_palette.py` ile kilitlidir.
    """
    from politikdesk.political_memory import service as mem_service

    return mem_service.search_actors(query=q, limit=limit, offset=offset)


@router.get("/search")
def unified_search(q: str = "", limit: int = 40) -> dict[str, Any]:
    """Komuta paletinin tek arama ucu (Roadmap Faz 8.2).

    Yedi tür tek listede döner ve her sonuç aynı sözleşmeyi taşır
    (`web/search.py::SearchHit`). Türe göre ayrı uç açılmamasının
    gerekçesi o modülün başlığında: D-02'de palet, sözleşmede olmayan
    iki anahtarı okuduğu için aktör aramasını sessizce hiç göstermiyordu
    — ne hata ne sonuç. Tek sözleşme, o hatanın tek yerde ölçülmesini
    sağlar.
    """
    from politikdesk.web import search as unified

    # Tavan istemciye bırakılmaz: palet en fazla ~40 satır gösterir ve
    # daha fazlasını istemek yalnızca veritabanını yorar.
    hits = unified.search(q, limit=max(1, min(int(limit), 60)))
    return {"query": q, "results": [hit.as_dict() for hit in hits]}


@router.get("/claims/{claim_id}/matrix")
def get_claim_matrix(claim_id: int) -> dict[str, Any]:
    """İddianın kanıt matrisi (Roadmap Faz 5.2).

    ⛔ Boyutlar tek bir "güven" sayısına ÇARPILMAZ. Karşı kanıt boyutu
    `unavailable` döner, `0` değil — o boyut bu üründe ölçülmüyor ve
    "0" göstermek kullanıcıya yanlışlıkla bir doğrulama sinyali verir
    (gerekçe: `docs/ADR-008-KARSI-KANIT-YOLU.md`).
    """
    from politikdesk.evidence.matrix import build

    m = build(claim_id)
    if m is None:
        raise HTTPException(status_code=404, detail="İddia bulunamadı.")
    return m.as_dict()


@router.get("/claims/matrix-coverage")
def get_claim_matrix_coverage() -> dict[str, Any]:
    """Matris boyutlarının canlı veride ne kadar dolabildiği.

    Bir boyut tüm iddialarda boşsa onu arayüzde göstermek yanıltır;
    bu uç o dürüstlük ölçüsünü verir.
    """
    from politikdesk.evidence.matrix import coverage_report

    return coverage_report()


@router.get("/memory/stance-shifts")
def list_memory_stance_shifts(limit: int = 50) -> list[dict[str, Any]]:
    """Sistem genelinde tespit edilen söylem değişikliklerini listeler."""
    from politikdesk.political_memory import service as mem_service

    return mem_service.list_all_stance_shifts(limit=limit)


@router.get("/memory/actors/{actor_name}/shifts")
def get_actor_shifts(actor_name: str) -> list[dict[str, Any]]:
    """Belirli bir aktörün söylem değişikliklerini döndürür."""
    from politikdesk.political_memory import service as mem_service

    return mem_service.get_actor_stance_shifts(actor_name=actor_name)


@router.get("/memory/compare")
def get_memory_comparison(
    actor: str = "Mehmet Şimşek",
    topic: str | None = None,
    year: int = 2025,
    limit: int = 50,
) -> dict[str, Any]:
    """Siyasi aktörün zamansal söylem karşılaştırma verisini döner."""
    from politikdesk.political_memory.comparison import compare_actor_statements

    res = compare_actor_statements(
        actor_name=actor,
        topic=topic if topic else None,
        split_year=year,
        limit=max(1, min(limit, 100)),
    )
    return res.to_dict()


@router.get("/memory/{actor}")
def get_actor_memory(actor: str) -> dict[str, Any]:
    """Aktör siyasi hafıza ve iddia kronolojisi (Spec §7.3, §8.3)."""
    from politikdesk.political_memory import service as mem_service

    memory = mem_service.get_actor_memory(actor)
    return memory.to_dict()



@router.get("/promises")
def list_promises() -> list[dict[str, Any]]:
    """Vaat takip listesi (Spec §7.3)."""
    from politikdesk.political_memory import service as mem_service

    return mem_service.get_promise_tracker()


@router.get("/accountability")
def get_accountability() -> list[dict[str, Any]]:
    """'Hesap Sor' hesap verebilirlik özeti."""
    from politikdesk.political_memory import service as mem_service

    return mem_service.get_accountability_digest()


@router.get("/accountability/cases")
def list_accountability_cases(limit: int = 50) -> dict[str, Any]:
    """S3 Hesap Verebilirlik Kanıt Kütüğü ve Olay İlişkileri (Spec v3.4 §14.1)."""
    from politikdesk.political_memory import service as mem_service
    from politikdesk.political_memory.accountability import LEGAL_DISCLAIMER
    from politikdesk.users import touch_last_seen

    user_id = current_user_id()
    touch_last_seen(user_id)

    cases = mem_service.get_accountability_digest(limit=limit)
    return {
        "total_cases": len(cases),
        "cases": cases,
        "disclaimer": LEGAL_DISCLAIMER,
    }


@router.get("/accountability/cases/{from_id}/{to_id}")
def get_accountability_case_detail(from_id: int, to_id: int) -> dict[str, Any]:
    """Tekil bir olay ilişkisinin detaylı kanıt dökümü (S3 Evidence Drawer)."""
    from politikdesk.db import connection
    from politikdesk.political_memory.accountability import LEGAL_DISCLAIMER
    from politikdesk.users import touch_last_seen

    user_id = current_user_id()
    touch_last_seen(user_id)

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT from_event_id, to_event_id, relation, similarity, confidence,
                   evidence_payload, status, engine_version, created_at, updated_at
            FROM event_relations
            WHERE from_event_id = %s AND to_event_id = %s;
            """,
            (from_id, to_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="İlişki kaydı bulunamadı.")

        return {
            "from_event_id": row["from_event_id"],
            "to_event_id": row["to_event_id"],
            "relation": row["relation"],
            "confidence": row["confidence"],
            "status": row["status"],
            "engine_version": row["engine_version"],
            "evidence_payload": row["evidence_payload"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "disclaimer": LEGAL_DISCLAIMER,
        }


@router.get("/feed")
def get_feed_items(
    sort: str = "important",
    category: str | None = None,
    topic: str | None = None,
    region: str | None = None,
    time_range: str | None = None,
    source_id: int | None = None,
    q: str | None = None,
    limit: int = 40,
    offset: int = 0,
) -> dict[str, Any]:
    """Gündem V2 — Live Intelligence Feed JSON ucu (Faz 21)."""
    user_id = current_user_id()
    items = repository.feed(
        user_id=user_id,
        limit=max(1, min(limit, 100)),
        offset=max(0, offset),
        sort=sort,
        category=category,
        topic=topic,
        region=region,
        time_range=time_range,
        source_id=source_id,
        query=q,
    )
    return {
        "items": items,
        "count": len(items),
        "sort": sort,
        "filters": {
            "category": category,
            "topic": topic,
            "region": region,
            "time_range": time_range,
            "source_id": source_id,
            "query": q,
        },
    }


@router.get("/feed/check-new")
def check_new_feed_items(
    since: str,
    category: str | None = None,
    region: str | None = None,
    vertical: str | None = None,
) -> dict[str, Any]:
    """İstemcinin son yenilemesinden bu yana gelen yeni aktif gelişme sayısını döner."""
    count = repository.count_new_events(
        since_ts=since,
        category=category,
        region=region,
        vertical=vertical,
    )
    return {"new_count": count, "since": since}


@router.get("/feed/taxonomy")
def get_feed_taxonomy() -> dict[str, Any]:
    """Gündem V2 kanonik kategori ve bölge sözlüğü."""
    from politikdesk.analysis.taxonomy import CATEGORIES, REGIONS

    return {
        "categories": [{"key": k, "label": lbl} for k, lbl in CATEGORIES],
        "regions": [{"key": k, "label": lbl} for k, lbl in REGIONS],
        "sort_modes": [
            {"key": "important", "label": "Önemli"},
            {"key": "newest", "label": "En Yeni"},
            {"key": "updated", "label": "Son Güncellenen"},
        ],
        "time_ranges": [
            {"key": "all", "label": "Tümü"},
            {"key": "15m", "label": "Son 15 dakika"},
            {"key": "1h", "label": "Son 1 saat"},
            {"key": "6h", "label": "Son 6 saat"},
            {"key": "24h", "label": "Son 24 saat"},
            {"key": "7d", "label": "Son 7 gün"},
        ],
    }


@router.get("/archive")
def get_archive(limit: int = 50) -> list[dict[str, Any]]:
    """Arşivlenmiş editoryal yayınlar ve kanıt kütüğü (Spec §14.4)."""
    from politikdesk.editorial.archive import list_archived_publications

    return list_archived_publications(limit=limit)


@router.get("/events/stream")
def live_events_stream() -> StreamingResponse:
    """Editoryal anlık bildirimler için Server-Sent Events (SSE) akışı (Spec v3.5 §14)."""

    from politikdesk.feature_flags import is_live_notifications_enabled
    from politikdesk.web.live_events import hub, sse_event_stream

    if not is_live_notifications_enabled():
        raise HTTPException(
            status_code=503,
            detail="Canlı bildirim akışı yapılandırma tarafından devre dışı bırakıldı.",
        )

    q = hub.subscribe()
    return StreamingResponse(
        sse_event_stream(q, timeout=15.0),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/accountability/search")
def search_accountability_digest(
    q: str = "", status: str = "all", limit: int = 50, offset: int = 0
) -> dict[str, Any]:
    """Hesap Sor vaat/icraat kayıtlarını sunucu tarafında arar ve sayfalar."""
    from politikdesk.political_memory import service as mem_service

    return mem_service.search_accountability(
        query=q, status_filter=status, limit=limit, offset=offset
    )


@router.get("/events/{event_id}/evidence-card")
def get_event_evidence_card(event_id: int) -> dict[str, Any]:
    """Olayın kanıt durumunu, kaynak dağılımını ve iddialarını dışa aktarılabilir kart formatında döner."""
    user_id = current_user_id()
    data = repository.event_page(event_id, user_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Olay bulunamadı.")

    ev = data["event"]
    claims = data["claims"]
    articles = data["articles"]

    return {
        "event_id": ev["id"],
        "title": ev["title"],
        "salience_score": ev.get("salience_score", 0),
        "status": ev.get("status", "developing"),
        "has_primary_source": ev.get("has_primary_source", False),
        "independence_groups": ev.get("independence_groups", 0),
        "article_count": len(articles),
        "claim_count": len(claims),
        "claims": [
            {
                "claim_id": c["id"],
                "text": c["claim_text"],
                "type": c["claim_type"],
                "evidence_status": c["evidence_status"],
                "evidence_count": c.get("evidence_count", 0),
            }
            for c in claims
        ],
        "sources": [
            {
                "name": a.get("source_name"),
                "tier": a.get("tier"),
                "kind": a.get("kind"),
            }
            for a in articles
        ],
    }


@router.get("/events/{event_id}/blindspot")
def get_event_blindspot(event_id: int) -> dict[str, Any]:
    """Olayın medya kör noktası ve kaynak dağılım analizini döner."""
    from politikdesk.evidence.blindspot import analyze_blindspot

    user_id = current_user_id()
    data = repository.event_page(event_id, user_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Olay bulunamadı.")

    articles = data["articles"]
    source_names = [a.get("source_name") or a.get("slug", "") for a in articles]
    report = analyze_blindspot(event_id=event_id, covered_sources=source_names)
    return report.to_dict()


def render_evidence_card_svg(
    ev: dict[str, Any],
    claims: list[dict[str, Any]],
    articles: list[dict[str, Any]],
    *,
    ratio: str = "16:9",
) -> str:
    """Olayın kanıt kartını görsel SVG olarak derler (16:9 veya 1:1 formatında, DESIGN.md token sistemiyle tam uyumlu)."""
    import hashlib
    from html import escape

    from politikdesk.web.ui.tokens import DARK

    bg = DARK["color-bg"]
    surface = DARK["color-surface"]
    border = DARK["color-border"]
    fg = DARK["color-fg"]
    fg_muted = DARK["color-fg-muted"]
    fg_subtle = DARK["color-fg-subtle"]
    accent = DARK["color-accent"]

    status_color_map = {
        "strongly_corroborated": DARK["color-strong"],
        "partially_corroborated": DARK["color-partial"],
        "single_source": DARK["color-single"],
        "contradicted": DARK["color-contra"],
        "unverified": DARK["color-unverified"],
        "attribution_verified": DARK["color-accent"],
    }
    status_label_map = STATUS_LABELS

    ev_title = escape(str(ev.get("title", "Olay")))
    salience = ev.get("salience_score", 0)
    top_status = claims[0].get("evidence_status", "unverified") if claims else "unverified"
    badge_color = status_color_map.get(top_status, DARK["color-unverified"])
    badge_text = status_label_map.get(top_status, "BELİRSİZ")

    provenance_raw = f"{ev.get('id')}:{ev.get('title')}:{salience}:{len(claims)}:{len(articles)}"
    sha_fingerprint = hashlib.sha256(provenance_raw.encode("utf-8")).hexdigest()[:12].upper()

    src_names = [escape(str(a.get("source_name") or a.get("slug") or "Kaynak")) for a in articles[:4]]
    src_str = " · ".join(src_names) if src_names else "Resmî ve Bağımsız Kaynaklar"
    if len(articles) > 4:
        src_str += f" (+{len(articles)-4} kaynak)"

    ind_groups = int(ev.get("independence_groups") or 0)
    ind_groups_str = f"{ind_groups} Farklı Yayın Grubu" if ind_groups >= 2 else "Tek Yayın Grubu"

    is_square = ratio in ("1:1", "square")
    width = 800
    height = 800 if is_square else 450

    claim_count_limit = 5 if is_square else 3
    claim_svg_elements = []
    y_pos = 180 if is_square else 165
    step_y = 52 if is_square else 44

    for c in claims[:claim_count_limit]:
        c_status = c.get("evidence_status", "unverified")
        c_color = status_color_map.get(c_status, DARK["color-unverified"])
        raw_text = str(c.get("claim_text", "")).strip()
        max_len = 80 if is_square else 75
        c_text = escape(raw_text[:max_len] + ("…" if len(raw_text) > max_len else ""))
        c_tag = status_label_map.get(c_status, "BİLGİ")
        claim_svg_elements.append(
            f'<g transform="translate(40, {y_pos})">'
            f'<rect x="0" y="0" width="720" height="{step_y - 10}" rx="8" fill="{surface}" fill-opacity="0.6" stroke="{border}" stroke-width="1" />'
            f'<circle cx="20" cy="17" r="5" fill="{c_color}" />'
            f'<text x="36" y="21" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="700" fill="{c_color}">[{c_tag}]</text>'
            f'<text x="175" y="21" font-family="system-ui, -apple-system, sans-serif" font-size="13" fill="{fg}">{c_text}</text>'
            f'</g>'
        )
        y_pos += step_y

    extra_section = ""
    if is_square:
        extra_section = f"""
  <g transform="translate(40, 520)">
    <rect x="0" y="0" width="720" height="150" rx="10" fill="{surface}" stroke="{border}" stroke-width="1" />
    <text x="24" y="32" font-family="system-ui, -apple-system, sans-serif" font-size="12" font-weight="700" letter-spacing="1" fill="{accent}">TEYİT HAVUZU VE METRİK DAĞILIMI</text>
    <text x="24" y="65" font-family="system-ui, -apple-system, sans-serif" font-size="13" fill="{fg}">• Bağımsızlık Durumu: <tspan font-weight="700" fill="{badge_color}">{ind_groups_str}</tspan></text>
    <text x="24" y="95" font-family="system-ui, -apple-system, sans-serif" font-size="13" fill="{fg}">• Kaynak Dağılımı: <tspan fill="{fg_muted}">{src_str}</tspan></text>
    <text x="24" y="125" font-family="system-ui, -apple-system, sans-serif" font-size="12" fill="{fg_subtle}">• Doğrulama İmzası: <tspan font-family="ui-monospace, monospace" fill="{fg_muted}">SHA256:{sha_fingerprint}</tspan></text>
  </g>
"""

    footer_y = height - 32

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <linearGradient id="cardGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{surface}" />
      <stop offset="100%" stop-color="{bg}" />
    </linearGradient>
    <linearGradient id="badgeGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{badge_color}" stop-opacity="0.25" />
      <stop offset="100%" stop-color="{badge_color}" stop-opacity="0.08" />
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" rx="16" fill="url(#cardGrad)" stroke="{border}" stroke-width="1.5" />

  <!-- Üst Başlık & Mühür -->
  <g transform="translate(40, 36)">
    <text font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="700" letter-spacing="1.5" fill="{accent}">POLİTİKDESK · DOĞRULANMIŞ İSTİHBARAT KARTI</text>
    <rect x="560" y="-14" width="160" height="28" rx="6" fill="url(#badgeGrad)" stroke="{badge_color}" stroke-width="1" />
    <text x="640" y="4" text-anchor="middle" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="700" fill="{badge_color}">{badge_text}</text>
  </g>

  <!-- Olay Başlığı & KPI Şeridi -->
  <g transform="translate(40, 78)">
    <text font-family="system-ui, -apple-system, sans-serif" font-size="16" font-weight="700" fill="{fg}">
      <tspan x="0" dy="0">{ev_title[:70]}</tspan>
      {"<tspan x='0' dy='22'>" + ev_title[70:140] + "</tspan>" if len(ev_title) > 70 else ""}
    </text>
    <text x="0" y="48" font-family="system-ui, -apple-system, sans-serif" font-size="11" fill="{fg_muted}">Gündem Ağırlığı: <tspan font-weight="700" fill="{fg}">{salience}/90</tspan> · <tspan fill="{fg}">{len(articles)} Kaynak</tspan> · <tspan fill="{fg}">{ind_groups_str}</tspan></text>
  </g>

  <line x1="40" y1="140" x2="760" y2="140" stroke="{border}" stroke-width="1" />

  <!-- Doğrulanmış İddialar -->
  {"".join(claim_svg_elements)}

  <!-- Ek Bilgi (1:1 ise) -->
  {extra_section}

  <!-- Alt Bilgi / Provenance -->
  <g transform="translate(40, {footer_y})">
    <line x1="0" y1="-14" x2="720" y2="-14" stroke="{border}" stroke-width="1" />
    <text font-family="system-ui, -apple-system, sans-serif" font-size="11" fill="{fg_subtle}">Doğrulama İmzası: <tspan font-family="ui-monospace, monospace">{sha_fingerprint}</tspan> · Kaynak: {src_names[0] if src_names else 'Resmî'}</text>
    <text x="720" y="0" text-anchor="end" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="700" fill="{accent}">politikdesk.com</text>
  </g>
</svg>"""
    return svg


@router.get("/events/{event_id}/evidence-card.svg")
def get_event_evidence_card_svg(event_id: int, ratio: str = "16:9") -> Response:
    """Olayın kanıt kartını doğrudan SVG görsel olarak döndürür (ratio: 16:9 veya 1:1)."""
    user_id = current_user_id()
    data = repository.event_page(event_id, user_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Olay bulunamadı.")

    svg_content = render_evidence_card_svg(data["event"], data["claims"], data["articles"], ratio=ratio)
    return Response(content=svg_content, media_type="image/svg+xml; charset=utf-8")


@router.get("/events/{event_id}/export")
def export_event_dossier(
    event_id: int,
    format: Literal[
        "markdown",
        "text",
        "factsheet",
        "json",
        "svg",
        "x_thread",
        "linkedin",
        "instant",
        "podcast",
        "bluesky",
        "mastodon",
        "newsletter",
    ] = "markdown",
    ratio: str = "16:9",
) -> Any:
    """Olayı ve kanıt zincirini istenen formatta dışa aktarır."""
    from fastapi.responses import PlainTextResponse

    from politikdesk.web.export_formats import (
        to_audio_script,
        to_bluesky_post,
        to_instant_dispatch,
        to_linkedin_brief,
        to_mastodon_post,
        to_newsletter_markdown,
        to_x_thread,
    )

    user_id = current_user_id()
    data = repository.event_page(event_id, user_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Olay bulunamadı.")

    ev = data["event"]
    claims = data["claims"]
    articles = data["articles"]

    if format == "svg":
        svg_content = render_evidence_card_svg(ev, claims, articles, ratio=ratio)
        return Response(content=svg_content, media_type="image/svg+xml; charset=utf-8")

    if format == "json":
        return {
            "event": ev,
            "claims": claims,
            "sources": articles,
        }

    if format == "x_thread":
        tweets = to_x_thread(ev, claims, articles)
        return {
            "event_id": ev["id"],
            "tweet_count": len(tweets),
            "tweets": tweets,
            "formatted_text": "\n\n---\n\n".join(tweets),
        }

    if format == "bluesky":
        bsky_text = to_bluesky_post(ev, claims, articles)
        return PlainTextResponse(bsky_text, media_type="text/plain; charset=utf-8")

    if format == "mastodon":
        masto_text = to_mastodon_post(ev, claims, articles)
        return PlainTextResponse(masto_text, media_type="text/plain; charset=utf-8")

    if format == "newsletter":
        nl_text = to_newsletter_markdown(ev, claims, articles)
        return PlainTextResponse(nl_text, media_type="text/markdown; charset=utf-8")

    if format == "linkedin":
        li_text = to_linkedin_brief(ev, claims, articles)
        return PlainTextResponse(li_text, media_type="text/plain; charset=utf-8")

    if format == "instant":
        inst_text = to_instant_dispatch(ev, claims, articles)
        return PlainTextResponse(inst_text, media_type="text/plain; charset=utf-8")

    if format == "podcast":
        pod_text = to_audio_script(ev, claims, articles)
        return PlainTextResponse(pod_text, media_type="text/plain; charset=utf-8")

    if format == "text":
        lines = [
            f"POLİTİKDESK KANIT DOSYASI: {ev['title']}",
            "=" * 60,
            f"Olay No: #{ev['id']} | Kaynak Sayısı: {len(articles)} | İddia Sayısı: {len(claims)}",
            "",
            "İDDİALAR VE KANIT DURUMLARI:",
        ]
        for c in claims:
            lines.append(f"- [{c['evidence_status'].upper()}] {c['claim_text']}")
        lines.append("")
        lines.append("KAYNAKLAR:")
        for a in articles:
            lines.append(f"- {a.get('source_name')} ({a.get('tier', 'T2')})")
        return PlainTextResponse("\n".join(lines), media_type="text/plain; charset=utf-8")

    # Markdown / Factsheet
    md_lines = [
        f"# {ev['title']}",
        "",
        f"> **PolitikDesk Doğrulanmış İstihbarat Dosyası #{ev['id']}**",
        f"> Gündem Skoru: {ev.get('salience_score', 0)}/90 · Bağımsız Kaynak: {len(articles)}",
        "",
        "## Doğrulanmış İddialar ve Kanıt Zinciri",
        "",
    ]
    for c in claims:
        status_tag = STATUS_LABELS.get(c["evidence_status"], c["evidence_status"])
        md_lines.append(f"* **[{status_tag}]:** {c['claim_text']}")

    md_lines.extend(["", "## Kaynakça", ""])
    for a in articles:
        md_lines.append(f"* **{a.get('source_name')}** ({a.get('title', '')})")

    return PlainTextResponse("\n".join(md_lines), media_type="text/markdown; charset=utf-8")


# ------------------------------------------------------------------- söylem ve karar karşılaştırması (Stance Diff)
@router.get("/stance/diff")
def get_stance_diff(
    actor_name: str | None = None,
    shift_type: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Siyasi beyanlar ile TBMM tutanakları ve Resmî Gazete kararları arasındaki söylem değişimini döner."""
    from politikdesk.political_memory.shift_store import for_actor, list_all

    if actor_name:
        shifts = for_actor(actor_name, limit=limit)
    else:
        shifts = list_all(limit=limit, shift_type=shift_type)

    return {"count": len(shifts), "shifts": shifts}


# ------------------------------------------------------------------- makro anomali uyarıları
@router.get("/anomalies/alerts")
def get_anomaly_alerts() -> dict[str, Any]:
    """Aktif makro ekonomik anomali uyarılarını listeler."""
    from politikdesk.config import get_settings

    if not get_settings().enable_anomaly_alerts:
        raise HTTPException(
            status_code=403,
            detail="Makro anomali bildirim özelliği devre dışı (PD_ENABLE_ANOMALY_ALERTS=false).",
        )

    from politikdesk.analysis.anomaly_alerts import collect_recent_anomalies

    alerts = collect_recent_anomalies()
    return {
        "count": len(alerts),
        "alerts": [a.as_dict() for a in alerts],
    }


class AnomalyDispatchTestRequest(BaseModel):
    webhook_url: str
    format_type: Literal["generic", "discord", "slack"] = "generic"
    series_key: str | None = None


@router.post("/anomalies/dispatch-test")
def test_dispatch_anomaly(payload: AnomalyDispatchTestRequest) -> dict[str, Any]:
    """Test veya canlı anomali uyarısını webhook ucuna iletir."""
    from datetime import UTC, datetime

    from politikdesk.config import get_settings

    if not get_settings().enable_anomaly_alerts:
        raise HTTPException(
            status_code=403,
            detail="Makro anomali bildirim özelliği devre dışı (PD_ENABLE_ANOMALY_ALERTS=false).",
        )

    from politikdesk.analysis.anomaly_alerts import (
        MacroAnomalyAlert,
        collect_recent_anomalies,
        dispatch_anomaly_alert,
    )

    alerts = collect_recent_anomalies()
    target_alert = (
        next((a for a in alerts if a.series_key == payload.series_key), None)
        if payload.series_key
        else None
    )
    if not target_alert:
        target_alert = (
            alerts[0]
            if alerts
            else MacroAnomalyAlert(
                alert_id="test-demo",
                series_key="demo_series",
                series_label="Demo Test Göstergesi",
                current_value=45.2,
                previous_value=40.0,
                change_pct=13.0,
                severity="high",
                score=3.2,
                detected_at=datetime.now(UTC).isoformat(),
                summary="PolitikDesk test anomali bildirimi.",
            )
        )

    ok = dispatch_anomaly_alert(
        target_alert, payload.webhook_url, format_type=payload.format_type
    )
    return {"success": ok, "alert": target_alert.as_dict()}





# -------------------------------------------------------- omnichannel yayın
@router.get("/events/{event_id}/omnichannel")
def get_event_omnichannel(event_id: int) -> dict[str, Any]:
    """Bir olay için 4 platformluk omnichannel yayın paketini döner."""
    from politikdesk.editorial.omnichannel import build_omnichannel_package_from_event

    pkg = build_omnichannel_package_from_event(event_id)
    return pkg.to_dict()


@router.get("/drafts/{draft_id}/omnichannel")
def get_draft_omnichannel(draft_id: int) -> dict[str, Any]:
    """Bir taslak için omnichannel yayın paketini döner."""
    from politikdesk.editorial import repository as ed_repo
    from politikdesk.editorial.omnichannel import build_omnichannel_package_from_event

    draft = ed_repo.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Taslak bulunamadı.")

    pkg = build_omnichannel_package_from_event(
        event_id=draft["event_id"],
        draft_id=draft_id,
        custom_title=draft.get("title"),
        custom_body=draft.get("body"),
    )
    return pkg.to_dict()


# -------------------------------------------------------- Telegram ve Otomatik Taslak API Uçları
class TelegramTestRequest(BaseModel):
    bot_token: str | None = None
    chat_id: str | None = None


@router.post("/telegram/test")
def test_telegram_endpoint(payload: TelegramTestRequest | None = None) -> dict[str, Any]:
    """Telegram bot yapılandırmasını test etmek için örnek bildirim gönderir."""
    from politikdesk.telegram_notifier import send_telegram_test_message

    token = payload.bot_token if payload else None
    chat_id = payload.chat_id if payload else None
    return send_telegram_test_message(bot_token=token, chat_id=chat_id)


class AutoDraftTriggerRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=50)
    angle: str | None = None


@router.post("/drafts/auto-trigger")
def trigger_auto_drafts_endpoint(payload: AutoDraftTriggerRequest | None = None) -> dict[str, Any]:
    """Teyitli bekleyen olaylar için otomatik taslak üretim döngüsünü tetikler."""
    from politikdesk.editorial.auto_draft import process_pending_auto_drafts

    limit = payload.limit if payload else 5
    angle = payload.angle if payload else None
    return process_pending_auto_drafts(limit=limit, angle=angle)

