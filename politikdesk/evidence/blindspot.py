"""Medya Kör Noktası ve Çerçeveleme Analizi (Blindspot & Framing Radar).

⛔ MİMARİ KURAL (Spec §11.2, P4):
Bu modül deterministiktir. `politikdesk.llm` ve `politikdesk.editorial`
paketlerini import EDEMEZ.

Bu modül, bir olayın kayıtlı 16 kaynaklık evrende hangi kademeler
(T1 Resmi, T2 Ajans/Ana Akım, T3 Bağımsız) ve bağımsızlık grupları
tarafından haberleştirildiğini, hangi grupların sessiz kaldığını
ve haberin medya ekosistemindeki dağılım dengesini hesaplar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

BlindspotSeverity = Literal[
    "balanced",          # Hem T1/T2 hem T3 kaynaklar dengeli gördü
    "independent_only",   # Yalnızca bağımsız medya gördü (Ana akım kör noktası)
    "official_only",      # Yalnızca resmi kurumlar/T1 açıkladı
    "mainstream_only",    # Yalnızca T1/T2 ana akım gördü (Bağımsız medya henüz görmedi)
    "single_source",      # Tek bir kaynakta kaldı
    "minimal",           # Çok az kaynak
]


@dataclass(frozen=True)
class TierBreakdown:
    tier1_official: int = 0
    tier2_mainstream: int = 0
    tier3_independent: int = 0


@dataclass(frozen=True)
class BlindspotReport:
    """Bir olayın medya ekosistemindeki dağılımı ve kör nokta analizi."""

    event_id: int
    covered_sources: tuple[str, ...]
    missing_sources: tuple[str, ...]
    covered_count: int
    total_sources_count: int
    coverage_ratio: float
    tier_breakdown: TierBreakdown
    independence_groups_count: int
    severity: BlindspotSeverity
    summary_label: str
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "covered_sources": list(self.covered_sources),
            "missing_sources": list(self.missing_sources),
            "covered_count": self.covered_count,
            "total_sources_count": self.total_sources_count,
            "coverage_ratio": round(self.coverage_ratio, 3),
            "tier_breakdown": {
                "t1_official": self.tier_breakdown.tier1_official,
                "t2_mainstream": self.tier_breakdown.tier2_mainstream,
                "t3_independent": self.tier_breakdown.tier3_independent,
            },
            "independence_groups_count": self.independence_groups_count,
            "severity": self.severity,
            "summary_label": self.summary_label,
            "description": self.description,
            "metadata": self.metadata,
        }


# Bilinen varsayılan kaynak bilgileri ve kademeleri (D6 v3.4 standardı)
DEFAULT_SOURCE_TIERS: dict[str, int] = {
    # T1 Resmi
    "tcmb": 1,
    "tuik": 1,
    "hazine": 1,
    "resmi_gazete": 1,
    "tbmm": 1,
    "sayistay": 1,
    "cumhurbaskanligi": 1,
    # T2 Ajans / Ana Akım
    "anadolu_ajansi": 2,
    "aa": 2,
    "trt_haber": 2,
    "bloomberght": 2,
    "dunya": 2,
    "haberturk": 2,
    "cnn_turk": 2,
    "ntv": 2,
    # T3 Bağımsız / Sektörel
    "reuters": 3,
    "sozcu": 3,
    "cumhuriyet": 3,
    "t24": 3,
    "diken": 3,
    "ekonomim": 3,
    "evrensel": 3,
    "birgun": 3,
    "gazeteduvar": 3,
}

DEFAULT_INDEPENDENCE_MAP: dict[str, str] = {
    "tcmb": "official",
    "tuik": "official",
    "hazine": "official",
    "resmi_gazete": "official",
    "tbmm": "official",
    "sayistay": "official",
    "cumhurbaskanligi": "official",
    "anadolu_ajansi": "state_agency",
    "aa": "state_agency",
    "trt_haber": "state_agency",
    "bloomberght": "ciner_group",
    "haberturk": "ciner_group",
    "cnn_turk": "demiroren_group",
    "dunya": "dunya_group",
    "ntv": "dogus_group",
    "sozcu": "sozcu_group",
    "cumhuriyet": "cumhuriyet_group",
    "t24": "t24_independent",
    "diken": "diken_independent",
}


def analyze_blindspot(
    event_id: int,
    covered_sources: list[str] | tuple[str, ...],
    all_registered_sources: list[str] | tuple[str, ...] | None = None,
    source_tiers: dict[str, int] | None = None,
    independence_map: dict[str, str] | None = None,
) -> BlindspotReport:
    """Bir olayın medya kapsama ve kör nokta profilini hesaplar."""
    covered_slugs = tuple(
        dict.fromkeys(
            s.lower().strip().replace("-", "_").replace(" ", "_")
            for s in covered_sources
            if s
        )
    )

    if all_registered_sources:
        all_slugs = tuple(
            dict.fromkeys(
                s.lower().strip().replace("-", "_").replace(" ", "_")
                for s in all_registered_sources
                if s
            )
        )
    else:
        all_slugs = tuple(DEFAULT_SOURCE_TIERS.keys())

    tiers = source_tiers or DEFAULT_SOURCE_TIERS
    ind_map = independence_map or DEFAULT_INDEPENDENCE_MAP

    missing_slugs = tuple(s for s in all_slugs if s not in covered_slugs)

    t1_count = sum(1 for s in covered_slugs if tiers.get(s, 2) == 1)
    t2_count = sum(1 for s in covered_slugs if tiers.get(s, 2) == 2)
    t3_count = sum(1 for s in covered_slugs if tiers.get(s, 2) == 3)

    tier_breakdown = TierBreakdown(
        tier1_official=t1_count,
        tier2_mainstream=t2_count,
        tier3_independent=t3_count,
    )

    # Bağımsız sermaye/yayın grupları sayısı
    distinct_groups = {ind_map.get(s, f"grp_{s}") for s in covered_slugs}
    group_count = len(distinct_groups)

    total_count = max(len(all_slugs), 1)
    covered_count = len(covered_slugs)
    coverage_ratio = covered_count / total_count

    # Deterministik ciddiyet / durum kararı
    if covered_count <= 1:
        severity: BlindspotSeverity = "single_source"
        summary_label = "Tek Kaynaklı Kapsam"
        description = (
            "Olay henüz tek bir kaynak tarafından geçildi; diğer mecralar henüz doğrulamadı."
        )
    elif t3_count > 0 and t1_count == 0 and t2_count == 0:
        severity = "independent_only"
        summary_label = "Ana Akım Kör Noktası"
        description = (
            "Haber yalnızca bağımsız/özel basında yer buldu; resmî kurumlar ve ajanslar sessiz."
        )
    elif (t1_count > 0 or t2_count > 0) and t3_count == 0:
        severity = "mainstream_only"
        summary_label = "Ana Akım / Resmî Odaklı"
        description = (
            "Gelişme resmî veya ana akım kanallardan duyuruldu; bağımsız çerçeveleme henüz yok."
        )
    elif t1_count > 0 and (t2_count > 0 or t3_count > 0):
        severity = "balanced"
        summary_label = "Çok Katmanlı & Dengeli Dağılım"
        description = (
            "Haber hem resmî kaynak hem de bağımsız medya grupları tarafından çapraz doğrulandı."
        )
    else:
        severity = "minimal"
        summary_label = "Kısmi Kapsam"
        description = "Haber sınırlı sayıda mecrada yer aldı."

    return BlindspotReport(
        event_id=event_id,
        covered_sources=covered_slugs,
        missing_sources=missing_slugs,
        covered_count=covered_count,
        total_sources_count=total_count,
        coverage_ratio=coverage_ratio,
        tier_breakdown=tier_breakdown,
        independence_groups_count=group_count,
        severity=severity,
        summary_label=summary_label,
        description=description,
    )
