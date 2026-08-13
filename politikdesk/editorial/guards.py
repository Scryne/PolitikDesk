"""Üretim kapıları — taslak üretiminin ÖNÜNDEKİ engeller (F3-11, Spec §15).

Bu modül, "üretilmiş metni sonradan denetlemek" ile "üretimi hiç
başlatmamak" arasındaki farkı taşır. İkisi de gerekli ama aynı şey
değildir: bir kapı ihlal edildiğinde LLM çağrısı **yapılmaz** — ne
maliyet oluşur ne de kullanıcının "yine de kullanayım" diyebileceği bir
metin ortaya çıkar.

Zorlanan iki sözleşme maddesi:

| Kapı | Kaynak | Davranış |
|---|---|---|
| P1 — kanıtsız olayda üretim yok | Spec §14.1 kalem 15, Yol Haritası F3-11 | HTTP 409 |
| İsimli kişi + doğrulanmamış iddia | Spec §15 madde 10 | HTTP 409 |

**Kapılar API katmanında değil BURADA durur.** Sebep F3-11 DoD'sinin
ikinci yarısıdır: "API doğrudan çağrılsa da reddediyor". Kontrolü uç
noktaya koymak, ikinci bir çağıranın (worker, brifing, betik) kapıyı
sessizce atlamasına izin verirdi.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from politikdesk.nlp.entities import extract_people

BlockReason = Literal["no_claims", "no_evidence", "unverified_person_claim"]

# Spec §15 madde 10 muafiyeti: `prediction` tipi iddialar R0 gereği
# HER ZAMAN `unverified`'dır — kanıt yokluğundan değil, tip kısıtından
# (Spec §8.3 R0, "gelecek doğrulanamaz").
#
# Muafiyet olmasaydı "Bakan X enflasyonun düşeceğini öngördü" cümlesi,
# hakkında hiçbir isnat bulunmayan bir kişi yüzünden tüm olayın üretimini
# bloke ederdi. Madde 10'un koruduğu şey "belirli kişilere yönelik
# SUÇLAMA"dır; bir kişinin kendi tahminini aktarmak suçlama değildir.
#
# Bu yorum Spec v3.2 §15'e "Madde 10'un kapsamı: tahmin muafiyeti"
# başlığıyla işlendi (B-72). Muafiyet YALNIZCA tip kısıtından doğan
# `unverified`'ı kapsar: kanıt yokluğundan `unverified` kalan bir `fact`
# veya `attribution` iddiası isimli kişi içeriyorsa üretim hâlâ engellenir.
PERSON_GUARD_EXEMPT_TYPES: Final[frozenset[str]] = frozenset({"prediction"})

# Kapının baktığı durumlar. `contradicted` kasıtlı olarak DIŞARIDA:
# çelişkili bir iddia "dayanaksız" değil, "iki kaynak anlaşamıyor"
# demektir ve bunu yazmak gazetecilik, isnat değildir.
UNVERIFIED_STATUSES: Final[frozenset[str]] = frozenset({"unverified"})


def blocked_statuses() -> frozenset[str]:
    """Üretimi engelleyen kanıt durumları.

    Normalde yalnızca `unverified`. Election Mode açıksa `single_source`
    de eklenir (Spec §12.6 madde 1). Sabit yerine fonksiyon olması
    F4-15'in özüdür: mod açıldığında değişmesi gereken tek yer
    `config/election_mode.py`'dir, buradaki çağıranlar değil.
    """
    from config.election_mode import current

    mode = current()
    return mode.blocked_statuses if mode.enabled else UNVERIFIED_STATUSES


class GenerationBlocked(Exception):
    """Üretim bir ürün sözleşmesi maddesi tarafından engellendi.

    `reason` makine-okunur, `message` kullanıcıya gösterilebilir.
    API katmanı bunu 409'a çevirir (F3-11 DoD).
    """

    def __init__(self, reason: BlockReason, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.reason: BlockReason = reason
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return {"blocked": True, "reason": self.reason, "message": self.message, **self.details}


@dataclass(frozen=True)
class ClaimForGeneration:
    """Üretime girecek tek bir iddia ve kanıtı.

    Bu, `claims` + `evidence` tablolarının üretim için gereken kesitidir.
    Girdi olarak BAŞKA bir şey yoktur (F3-10 DoD: "girdi yalnızca
    claims+evidence").
    """

    claim_id: int
    claim_text: str
    claim_type: str
    evidence_status: str
    status_rule: str = ""
    normalized_value: dict[str, Any] | None = None
    evidence: tuple[dict[str, Any], ...] = ()

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)


def _named_people(claims: Sequence[ClaimForGeneration]) -> dict[int, list[str]]:
    """İddia başına, unvan kalıbıyla tanınan kişi adları.

    `extract_people` yalnızca unvanla anılan isimleri döndürür
    ("Bakan Mehmet Şimşek"); unvansız iki büyük harfli sözcüğü kişi
    saymaz. Bu kısıt burada bir avantajdır: kapı, kurum ve yer adları
    yüzünden yanlış tetiklenmez.
    """
    out: dict[int, list[str]] = {}
    for claim in claims:
        people = [p.canonical_name for p in extract_people(claim.claim_text)]
        if people:
            out[claim.claim_id] = people
    return out


def require_generation_allowed(claims: Sequence[ClaimForGeneration]) -> None:
    """Üretimin başlamasına izin var mı? Yoksa `GenerationBlocked` fırlatır."""
    if not claims:
        raise GenerationBlocked(
            "no_claims",
            "Bu olayda henüz çıkarılmış iddia yok. Kanıta bağlanmamış bir "
            "olaydan taslak üretilmez (Spec §14.1 kalem 15).",
        )

    if not any(c.evidence_count for c in claims):
        raise GenerationBlocked(
            "no_evidence",
            "Bu olayın iddialarının hiçbiri bir kaynağa bağlanmamış. "
            "Dayanacak kanıt olmadan taslak üretilmez (P1).",
            {"claim_count": len(claims)},
        )

    blocking = blocked_statuses()
    people_by_claim = _named_people(claims)
    offenders: list[dict[str, Any]] = [
        {
            "claim_id": claim.claim_id,
            "claim_text": claim.claim_text[:160],
            "people": people_by_claim[claim.claim_id],
        }
        for claim in claims
        if claim.claim_id in people_by_claim
        and claim.evidence_status in blocking
        and claim.claim_type not in PERSON_GUARD_EXEMPT_TYPES
    ]
    if offenders:
        names = sorted({name for o in offenders for name in o["people"]})
        raise GenerationBlocked(
            "unverified_person_claim",
            "Bu olayda isimli bir kişi hakkında doğrulanmamış iddia var "
            f"({', '.join(names)}). Ürün sözleşmesi (Spec §15 madde 10) "
            "böyle bir olayda taslak üretimini engeller.",
            {"claims": offenders},
        )


def generation_block_reason(claims: Sequence[ClaimForGeneration]) -> GenerationBlocked | None:
    """Kapıyı fırlatmadan sorar — UI butonu devre dışı bırakmak için.

    Aynı fonksiyonu iki kez yazmamak önemli: UI'ın "butonu kapat" kararı
    ile API'nin "409 döndür" kararı ayrışırsa, kullanıcı tıklayabildiği
    ama her seferinde hata alan bir buton görür.
    """
    try:
        require_generation_allowed(claims)
    except GenerationBlocked as blocked:
        return blocked
    return None


__all__ = [
    "ClaimForGeneration",
    "GenerationBlocked",
    "blocked_statuses",
    "generation_block_reason",
    "require_generation_allowed",
]
