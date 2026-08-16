"""Kanıt durumu kural motoru R0–R7 (F2-12, F2-13 · Spec v3.1 §8.3).

DoD: 8 kuralın her biri için birim testi; R0 kısa devresi ayrıca test
edilir; **modülde hiçbir LLM çağrısı yok** (CI kontrolü).

⛔ MİMARİ KURAL: bu modül `politikdesk.llm` import EDEMEZ.
`evidence_status` hiçbir koşulda bir LLM çıktısı olamaz (Spec §8.1).

Kurallar üç blok hâlinde ve bu sırayla uygulanır:

| Blok | Kurallar | Davranış |
|---|---|---|
| 1 — tip kısıtı | **R0** | Kanıta bakmaz; eşleşirse **kısa devre** |
| 2 — kanıt kuralları | R1–R6 | Sıralı, ilk eşleşen kazanır |
| 3 — tavan kısıtı | R7 | Blok 2'nin sonucunu yukarıdan sınırlar |

R0'ın başta olması v3.1'in düzelttiği çelişkidir (İtiraz-4): bir tahmin
hakkında hem destekleyen hem çelişen Tier 1–2 kanıt bulunması makro
ekonomide olağandır ("piyasa faizin düşeceğini bekliyor" / "yükseleceğini").
Eski sıralamada R1 kazanıyor ve tahmin 🔴 `contradicted` etiketleniyordu —
oysa çelişkili göstermek de bir doğrulama iddiasıdır.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from politikdesk.evidence.independence import (
    EvidenceArticle,
    breakdown_by_kind,
    group_by_independence,
    has_primary_source,
    independent_count,
)

ENGINE_VERSION = "evidence-engine@1.0.0"

EvidenceStatus = Literal[
    "strongly_corroborated",  # 🟢
    "partially_corroborated",  # 🟡
    "single_source",  # 🟠
    "contradicted",  # 🔴
    "unverified",  # ⚪
    "attribution_verified",  # 🔵 (Beyan Sabit - Spec v3.4 §8.1 / B-92)
]

ClaimType = Literal["fact", "number", "attribution", "prediction", "promise"]
Stance = Literal["supports", "contradicts", "partial"]

# Spec §9.2 — R3'ün "kurumun kendi yayını" istisnası bu kaynaklarla sınırlı.
OFFICIAL_STATISTICAL_SOURCES = frozenset({"tuik", "tcmb", "hazine", "resmi-gazete"})

# R8: Beyan ve tutanak birincil kayıt kaynakları (Spec v3.4 §8.3 / B-92)
OFFICIAL_RECORD_SOURCES = frozenset(
    {"tbmm-tutanak", "tbmm-kanun", "resmi-gazete", "sayistay", "cb-kararname", "tuik", "tcmb"}
)

# Durumların güç sırası — R7 tavan kısıtı bunu kullanır.
_STATUS_RANK: dict[str, int] = {
    "unverified": 0,
    "single_source": 1,
    "attribution_verified": 1,
    "partially_corroborated": 2,
    "strongly_corroborated": 3,
    "contradicted": 4,  # sıralamaya girmez; R7 zaten tetiklenemez
}


@dataclass(frozen=True)
class Evidence:
    """Bir iddia ile bir makale arasındaki kanıt bağı."""

    article: EvidenceArticle
    stance: Stance
    quote_span: str = ""

    @property
    def supports(self) -> bool:
        return self.stance == "supports"

    @property
    def contradicts(self) -> bool:
        return self.stance == "contradicts"


@dataclass(frozen=True)
class Claim:
    """Durumu hesaplanacak iddia."""

    claim_id: int
    claim_text: str
    claim_type: ClaimType
    normalized_value: dict | None = None
    # R3 için: değer, kurumun kendi yayın formatıyla doğrulandı mı?
    value_verified_against_source: bool = False


@dataclass(frozen=True)
class StatusResult:
    """Hesaplanmış durum + makine-okunur gerekçe (F2-13)."""

    status: EvidenceStatus
    rule: str
    reason: dict

    def as_status_reason(self) -> dict:
        return self.reason


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def strong_min_sources() -> int:
    """R2'nin bağımsız kaynak eşiği (Spec §8.3 R2, §12.6 madde 2).

    Normalde 3. Election Mode açıkken 4 — seçim döneminde 🟢 etiketi
    vermenin maliyeti, vermemenin maliyetinden yüksektir.
    """
    from config.election_mode import current

    return current().strongly_corroborated_min_sources


def engine_version() -> str:
    """Motorun *yürürlükteki* sürümü — mod dahil.

    Election Mode eşikleri değiştirdiği için, aynı kanıt setine farklı
    bir durum atanır. Sürüm dizesine modu yazmak, `score_claims`'in
    "sürümü farklı olanı yeniden puanla" yüklemini kendiliğinden
    tetikler: mod açıldığında tüm iddialar yeni eşiğe göre yeniden
    hesaplanır. Yazılmasaydı, mod açıkken eski gevşek etiketler
    ekranda kalırdı — göstergesi açık, koruması kapalı bir mod.
    """
    from config.election_mode import is_enabled

    return f"{ENGINE_VERSION}+election" if is_enabled() else ENGINE_VERSION


def _base_reason(rule: str) -> dict:
    return {"rule": rule, "computed_at": _now(), "engine_version": engine_version()}


# ---------------------------------------------------------------- R0
def _r0_prediction(claim: Claim) -> StatusResult | None:
    """R0 — tip kısıtı. Kanıta BAKMAZ, kısa devre yapar.

    Gerekçe: gelecek doğrulanamaz. Bu, haber/yorum ayrımının kod hâli.
    """
    if claim.claim_type != "prediction":
        return None
    return StatusResult(
        status="unverified",
        rule="R0",
        reason={
            **_base_reason("R0"),
            "short_circuit": "claim_type=prediction",
            "evaluated_evidence_rules": False,
            "label": "Tahmin",
        },
    )


# ---------------------------------------------------------------- R1–R6
def _r1_contradicted(evidence: list[Evidence]) -> bool:
    """En az bir taraf Tier 1–2 olmalı ki sosyal medya gürültüsü çelişki üretmesin."""
    supports = [e for e in evidence if e.supports and e.article.tier <= 3]
    contradicts = [e for e in evidence if e.contradicts and e.article.tier <= 3]
    if not supports or not contradicts:
        return False
    return any(e.article.tier <= 2 for e in supports + contradicts)


def _r3_official_number(claim: Claim, evidence: list[Evidence]) -> bool:
    """Resmî sayısal veri istisnası: TÜİK verisini TÜİK açıkladıysa 3 teyit beklenmez.

    Election Mode'da bu istisna KAPALIDIR. Spec §12.6 madde 2 "🟢 için
    independent_count ≥ 4 ve Tier 1 zorunlu" diyor; tek kaynağa 🟢
    veren bir istisnayı açık bırakmak o cümleyi boşa çıkarırdı.
    """
    from config.election_mode import current

    if current().enabled:
        return False
    if claim.claim_type != "number" or not claim.value_verified_against_source:
        return False
    return any(
        e.supports and e.article.tier == 1 and e.article.source_slug in OFFICIAL_STATISTICAL_SOURCES
        for e in evidence
    )


def _r8_attribution_verified(claim: Claim, evidence: list[Evidence]) -> bool:
    """R8: Resmî bir beyan birinci el tutanak veya resmî yayına bağlanmışsa (B-92).

    'attribution' tipindeki iddia, konuşmanın birincil kaydında (TBMM tutanağı,
    resmî gazete, kurum duyurusu vb.) yer alıyorsa beyanın yapıldığı sabittir.
    İçeriğin doğruluğu ayrıdır; statü 'attribution_verified' (Beyan Sabit) olur.
    """
    if claim.claim_type != "attribution":
        return False
    return any(
        e.supports
        and e.article.tier == 1
        and (e.article.source_slug in OFFICIAL_RECORD_SOURCES or e.article.kind == "official")
        for e in evidence
    )


def compute_status(
    claim: Claim,
    evidence: list[Evidence],
    *,
    partial_elements: bool = False,
) -> StatusResult:
    """İddianın kanıt durumunu hesaplar.

    `partial_elements`: iddianın bazı unsurları yalnız tek kaynakta
    doğrulanmışsa (R4'ün ikinci koşulu). Bu bilgi iddia çıkarımından
    (F2-10) gelir; kural motoru üretmez.
    """
    # ---- BLOK 1: tip kısıtı, kısa devre
    short_circuit = _r0_prediction(claim)
    if short_circuit is not None:
        return short_circuit

    supporting = [e.article for e in evidence if e.supports]
    contradicting = [e for e in evidence if e.contradicts and e.article.tier <= 3]
    count = independent_count(supporting)
    primary = has_primary_source(supporting)
    breakdown = breakdown_by_kind(supporting)

    facts = {
        "independent_count": count,
        "breakdown": breakdown,
        "has_primary_source": primary,
        "contradictions": len(contradicting),
        "independence_keys": sorted(group_by_independence(supporting)),
    }

    # ---- BLOK 2: kanıt kuralları, ilk eşleşen kazanır
    corroborating_count = independent_count([a for a in supporting if a.tier <= 3])
    if _r1_contradicted(evidence):
        result = StatusResult("contradicted", "R1", {**_base_reason("R1"), **facts})
    elif primary and corroborating_count >= strong_min_sources() and not contradicting:
        result = StatusResult("strongly_corroborated", "R2", {**_base_reason("R2"), **facts})
    elif _r3_official_number(claim, evidence):
        result = StatusResult(
            "strongly_corroborated",
            "R3",
            {
                **_base_reason("R3"),
                **facts,
                "exception": "official_numeric_publication",
                "normalized_value": claim.normalized_value,
            },
        )
    elif _r8_attribution_verified(claim, evidence):
        result = StatusResult(
            "attribution_verified",
            "R8",
            {
                **_base_reason("R8"),
                **facts,
                "label": "Beyan Sabit",
                "exception": "primary_official_attribution_record",
            },
        )
    elif count >= 2:
        result = StatusResult(
            "partially_corroborated",
            "R4",
            {**_base_reason("R4"), **facts, "partial_elements": partial_elements},
        )
    elif count == 1:
        result = StatusResult("single_source", "R5", {**_base_reason("R5"), **facts})
    else:
        result = StatusResult("unverified", "R6", {**_base_reason("R6"), **facts})

    # ---- BLOK 3: tavan kısıtı, sonuca uygulanır
    return _apply_r7_ceiling(result, supporting)


def _apply_r7_ceiling(result: StatusResult, supporting: list[EvidenceArticle]) -> StatusResult:
    """R7 — yalnızca Tier 4 (sosyal) kanıt varsa azami `single_source`.

    Sayı kaç olursa olsun 🟢/🟡 olamaz: sosyal medyada bir iddianın çok
    kez tekrarlanması onu doğrulamaz.
    """
    if not supporting or any(a.tier <= 3 for a in supporting):
        return result
    if _STATUS_RANK[result.status] <= _STATUS_RANK["single_source"]:
        return result

    return StatusResult(
        status="single_source",
        rule="R7",
        reason={
            **result.reason,
            "rule": "R7",
            "capped_from": result.status,
            "capped_by_rule": result.rule,
            "ceiling_reason": "all_evidence_is_tier_4_social",
        },
    )
