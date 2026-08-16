"""Editoryal akışın orkestrasyonu (F3-10 … F3-15).

Zincir: **kapı → üretim → grounding → pre-publish check → kayıt.**

Bu sıra pazarlık edilebilir değil. Her adım bir öncekinin çıktısını
denetler ve hiçbiri atlanamaz:

    guards.require_generation_allowed()   LLM çağrısından ÖNCE (F3-11)
    generator.generate_draft()            girdi yalnızca claims+evidence
      └─ grounding_check.check()          kanıtta olmayan sayı/tarih (F3-12)
    checker.run_checks()                  Spec §14.4'ün altı kontrolü (F3-13)
    repository.save_draft()               grounding düşse bile kaydedilir

**Neden grounding'i düşen taslak da kaydediliyor:** kapı G3 koşul 2
("kanıtta olmayan sayı/tarih = %0") bir ORANDIR. Düşenleri silmek
paydayı yok eder ve oran her koşulda %0 çıkar — ölçüm kendi kendini
doğrular hâle gelirdi.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from politikdesk import audit
from politikdesk.editorial import repository
from politikdesk.editorial.checker import run_checks
from politikdesk.editorial.generator import ANGLES, GeneratedDraft, generate_draft
from politikdesk.editorial.guards import (
    GenerationBlocked,
    GroundingBlocked,
    generation_block_reason,
)
from politikdesk.editorial.profile_compiler import compiled_prompt_for, load_profile
from politikdesk.observability import get_logger

log = get_logger(__name__)

USER_ACTIONS = ("accepted", "edited", "regenerated", "rejected")


# --------------------------------------------------------- düzenleme mesafesi
def levenshtein(a: str, b: str) -> int:
    """Klasik düzenleme mesafesi, iki satırlık DP ile.

    Kütüphane yerine 20 satır: taslak gövdesi ≤ 600 karakter olduğu için
    O(n·m) burada ölçülemeyecek kadar hızlıdır ve tek bir bağımlılık
    eklemeye değmez.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, ch_a in enumerate(a, start=1):
        current = [i]
        for j, ch_b in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,  # silme
                    current[j - 1] + 1,  # ekleme
                    previous[j - 1] + (ch_a != ch_b),  # değiştirme
                )
            )
        previous = current
    return previous[-1]


def normalized_edit_distance(original: str, final: str) -> float:
    """0 = hiç değişmemiş, 1 = tamamen yeniden yazılmış (Spec §13.3).

    Payda uzun metindir: kısa metne göre normalleştirmek, metni
    kısaltan bir düzenlemeyi 1'in üstüne taşırdı.
    """
    original, final = original or "", final or ""
    longest = max(len(original), len(final))
    if longest == 0:
        return 0.0
    return round(levenshtein(original, final) / longest, 4)


# ------------------------------------------------------------------ üretim
def can_generate(event_id: int) -> dict[str, Any]:
    """Bu olayda üretim mümkün mü? (F3-11 — UI butonunun durumu)

    API'nin 409 kararıyla aynı fonksiyonu kullanır; ikisi ayrışırsa
    kullanıcı tıklanabilir ama her seferinde hata veren bir buton görür.
    """
    claims = repository.load_claims_for_generation(event_id)
    blocked = generation_block_reason(claims)
    if blocked is not None:
        return {"allowed": False, "claim_count": len(claims), **blocked.as_dict()}
    return {
        "allowed": True,
        "claim_count": len(claims),
        "evidence_count": sum(c.evidence_count for c in claims),
    }


def _prior_context(event_id: int, limit: int = 3) -> list[str]:
    """Olayın `same_thread` bağlarının başlıkları (F2-17 çıktısı).

    Yalnızca pre-publish check'in 6. kontrolüne (eksik bağlam) girer;
    ÜRETİM PROMPTUNA GİRMEZ (F3-10 girdi sözleşmesi).
    """
    from politikdesk.db import connection

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.title
            FROM event_relations r
            JOIN events e ON e.id = r.to_event_id
            WHERE r.from_event_id = %s AND r.relation = 'same_thread'
              AND e.merged_into_id IS NULL
            ORDER BY r.similarity DESC NULLS LAST
            LIMIT %s
            """,
            (event_id, limit),
        )
        return [r["title"] for r in cur.fetchall()]


def generate_for_event(
    *,
    event_id: int,
    angle: str,
    user_id: int,
    client: Any | None = None,
    persist: bool = True,
    stance_path: Path | None = None,
) -> dict[str, Any]:
    """Bir olay için tek açılı taslak üretir, denetler ve kaydeder.

    `GenerationBlocked` YUTULMAZ — çağıran katman onu 409'a çevirir
    (F3-11 DoD: "API doğrudan çağrılsa da reddediyor").
    """
    if angle not in ANGLES:
        raise ValueError(f"Bilinmeyen açı: {angle!r}")

    claims = repository.load_claims_for_generation(event_id)
    if client is None:
        from politikdesk.llm.client import LLMClient

        client = LLMClient()

    from politikdesk.editorial.stance import get_stance_prompt_block

    base_block = compiled_prompt_for(user_id)
    stance_block = get_stance_prompt_block(stance_path)
    profile_block = f"{base_block}\n\n{stance_block}" if stance_block else base_block

    draft: GeneratedDraft = generate_draft(
        angle=angle,
        claims=claims,
        client=client,
        profile_block=profile_block,
        user_id=user_id,
    )

    check_report = run_checks(
        draft,
        claims,
        prior_context=_prior_context(event_id),
        grounding=draft.grounding,
        # Profil biçim denetimi (F5-21): modelin promptu dinlediğine
        # GÜVENİLMEZ. Ölçüldü — bir model "emoji kullanma" yazılıyken
        # taslağa emoji ve hashtag ekledi.
        profile=load_profile(user_id),
    )

    payload: dict[str, Any] = {
        **draft.as_dict(),
        "event_id": event_id,
        "check": check_report.as_dict(),
    }

    if persist:
        draft_id = repository.save_draft(
            user_id=user_id,
            event_id=event_id,
            angle=angle,
            body=draft.body,
            cited_claim_ids=list(draft.cited_claim_ids),
            grounding_result=draft.grounding.as_dict(),
            is_grounded=draft.is_grounded,
            check_result=check_report.as_dict(),
            model=draft.model,
            prompt_version=draft.prompt_version,
        )
        payload["draft_id"] = draft_id

        # F4-16: taslak üretimi denetim izine düşer. `draft_action` zaten
        # kaydediliyordu ama o KULLANICININ tepkisidir; üretimin kendisi
        # — hangi modelin, hangi promptla, hangi iddialara dayanarak
        # yazdığı — kayıtsızdı. Bir taslak geriye dönük sorgulanacaksa
        # sorulacak ilk soru budur.
        audit.write(
            "draft_generated",
            f"drafts/{draft_id}",
            actor=f"user:{user_id}",
            payload={
                "event_id": event_id,
                "angle": angle,
                "model": draft.model,
                "prompt_version": draft.prompt_version,
                "cited_claim_ids": list(draft.cited_claim_ids),
                "is_grounded": draft.is_grounded,
                "is_blocking": check_report.as_dict().get("is_blocking", False),
            },
        )

    return payload


def generate_all_angles(
    *,
    event_id: int,
    user_id: int,
    client: Any | None = None,
    stance_path: Path | None = None,
) -> dict[str, Any]:
    """Üç açının hepsini üretir (Spec §14.3 "EDİTORYAL FIRSATLAR").

    Bir açının düşmesi diğerlerini düşürmez; kapı ihlali ise hepsini
    birden durdurur çünkü kapı olaya aittir, açıya değil.
    """
    results: dict[str, Any] = {}
    for angle in ANGLES:
        try:
            results[angle] = generate_for_event(
                event_id=event_id,
                angle=angle,
                user_id=user_id,
                client=client,
                stance_path=stance_path,
            )
        except GenerationBlocked:
            raise
        except Exception as exc:  # noqa: BLE001 — bir açı diğerlerini düşürmez
            log.warning(
                "angle_generation_failed",
                event_id=event_id,
                angle=angle,
                error=type(exc).__name__,
            )
            results[angle] = {
                "angle": angle,
                "error": type(exc).__name__,
                "message": str(exc)[:200],
            }
    return {"event_id": event_id, "drafts": results}


# ----------------------------------------------------------------- aksiyon
def apply_action(*, draft_id: int, action: str, final_body: str | None = None) -> dict[str, Any]:
    """Kullanıcı aksiyonunu kaydeder ve `edit_distance`'ı hesaplar (F3-14).

    `edit_distance` yalnızca `edited` aksiyonunda anlamlıdır. `accepted`
    için 0 yazılır (metin değişmedi), diğerlerinde NULL kalır: reddedilen
    bir taslağın düzenleme mesafesi "0" değil, "yok"tur.
    """
    if action not in USER_ACTIONS:
        raise ValueError(f"Bilinmeyen aksiyon: {action!r}. Seçenekler: {list(USER_ACTIONS)}")

    draft = repository.get_draft(draft_id)
    if draft is None:
        raise LookupError(f"Taslak yok: {draft_id}")

    if action == "accepted" and not draft.get("is_grounded", True):
        raise GroundingBlocked(
            f"Taslak #{draft_id} grounding denetiminden geçmediği için doğrudan kabul edilemez.",
            details={"draft_id": draft_id, "is_grounded": False},
        )

    distance: float | None = None
    stored_body: str | None = None

    if action == "accepted":
        stored_body = final_body or draft["body"]
        if final_body and final_body != draft["body"]:
            distance = normalized_edit_distance(draft["body"], final_body)
        else:
            distance = 0.0
    elif action == "edited":
        if not final_body:
            raise ValueError("'edited' aksiyonu düzenlenmiş metni gerektirir.")
        stored_body = final_body
        distance = normalized_edit_distance(draft["body"], final_body)

    row = repository.record_action(draft_id, action, stored_body, distance)

    # Arşiv kütüğü ve denetim manifestosu oluşturulup kalıcılaştırılır (Spec §14.4)
    if action in ("accepted", "edited"):
        try:
            from politikdesk.editorial.archive import persist_draft_archive

            persist_draft_archive(draft_id, stored_body)
        except Exception as exc:  # noqa: BLE001
            log.warning("draft_archive_persist_failed", draft_id=draft_id, error=str(exc))

    # Ham iz metriğe de yazılır: `drafts` tablosu silinse bile ölçüm
    # geçmişi `metrics` tablosunda durur (Spec §13.3).
    from politikdesk import metrics

    if distance is not None:
        metrics.record(
            "edit_distance",
            distance,
            user_id=draft["user_id"],
            dimensions={"draft_id": draft_id, "action": action, "angle": draft["angle"]},
        )

    log.info("draft_action", draft_id=draft_id, action=action, edit_distance=distance)
    return {**row, "edit_distance": distance}


def publish_payload(draft_id: int) -> dict[str, Any]:
    """Yayın köprüsü için metin ve X Web Intent adresi (F3-15).

    ⛔ **Otomatik gönderim yok.** Burada üretilen tek şey, kullanıcının
    yeni sekmede açacağı bir `intent/tweet` ADRESİDİR. Ürün sözleşmesi
    (Spec §15 madde 6, P5) insan onayı olmadan yayını yasaklar ve bu
    dosyada X'e giden hiçbir POST kod yolu bulunmaz.
    """
    from urllib.parse import quote

    draft = repository.get_draft(draft_id)
    if draft is None:
        raise LookupError(f"Taslak yok: {draft_id}")

    if not draft.get("is_grounded", True):
        raise GroundingBlocked(
            f"Taslak #{draft_id} grounding denetiminden geçmediği için yayınlanamaz.",
            details={"draft_id": draft_id, "is_grounded": False},
        )

    text = draft.get("final_body") or draft["body"]
    return {
        "draft_id": draft_id,
        "text": text,
        # Web Intent: tarayıcıda açılır, kullanıcı gönder'e KENDİ basar.
        "web_intent_url": f"https://x.com/intent/tweet?text={quote(text, safe='')}",
        "requires_human_send": True,
    }
