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
    angle: Literal["inform", "analyze", "critique"]


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
        return service.generate_for_event(
            event_id=event_id, angle=payload.angle, user_id=user_id
        )
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
            detail={"message": f"Model çağrısı başarısız: {type(exc).__name__}",
                    "reason": "llm_error"},
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
    """"Bu yanlış" (F3-21) — olayı denetim kuyruğuna düşürür."""
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
