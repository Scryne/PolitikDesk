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

from fastapi import APIRouter, HTTPException, Request
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

    record_activity(
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


# --------------------------------------------------------------- siyaset dikeyi
@router.get("/memory/actors")
def search_memory_actors(q: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """Siyasi hafıza aktörlerini filtreler ve sayfalar."""
    from politikdesk.political_memory import service as mem_service

    return mem_service.search_actors(query=q, limit=limit, offset=offset)


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


@router.get("/events/{event_id}/export")
def export_event_dossier(
    event_id: int, format: Literal["markdown", "text", "factsheet", "json"] = "markdown"
) -> Any:
    """Olayı ve kanıt zincirini istenen formatta dışa aktarır."""
    from fastapi.responses import PlainTextResponse

    user_id = current_user_id()
    data = repository.event_page(event_id, user_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Olay bulunamadı.")

    ev = data["event"]
    claims = data["claims"]
    articles = data["articles"]

    if format == "json":
        return {
            "event": ev,
            "claims": claims,
            "sources": articles,
        }

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
        status_tag = {
            "strongly_corroborated": "[Güçlü Teyitli]",
            "partially_corroborated": "[Kısmen Teyitli]",
            "single_source": "[Tek Kaynaklı]",
            "contradicted": "[Çelişkili]",
            "unverified": "[Doğrulanmamış]",
            "attribution_verified": "[Beyan Sabit]",
        }.get(c["evidence_status"], f"[{c['evidence_status']}]")
        md_lines.append(f"* **{status_tag}:** {c['claim_text']}")

    md_lines.extend(["", "## Kaynakça", ""])
    for a in articles:
        md_lines.append(f"* **{a.get('source_name')}** ({a.get('title', '')})")

    return PlainTextResponse("\n".join(md_lines), media_type="text/markdown; charset=utf-8")


