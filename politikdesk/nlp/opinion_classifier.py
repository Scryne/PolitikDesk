"""Haber / Yorum ve Köşe Yazısı Sınıflandırıcı (B-97 · Spec v3.4 §5, §14.4).

Siyaset kaynaklarında köşe yazısı, kulis dedikodusu ve sübjektif yorum
oranı yüksektir. Bu filtre, bir makalenin veya metin bloğunun haber/olay mı
yoksa köşe yazısı/yorum mu olduğunu deterministik göstergelerle ayırt eder.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from politikdesk.nlp.claims import fold_text

_OPINION_COLUMN_HINTS_RAW: Final[tuple[str, ...]] = (
    "köşe yazısı",
    "yazarlar",
    "köşe yazarları",
    "günün yazısı",
    "başyazı",
    "yorum",
    "analiz-yorum",
    "kulis",
    "kulis bilgisi",
    "başkent kulisi",
    "meclis kulisi",
    "gözlem",
    "değerlendirme",
)
_OPINION_COLUMN_HINTS: Final[tuple[str, ...]] = tuple(
    dict.fromkeys(fold_text(h) for h in _OPINION_COLUMN_HINTS_RAW)
)

_OPINION_TITLE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^[A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s*:\s*"),  # "Yazar Adı: Başlık"
    re.compile(r"\b(yazdı|kaleme aldı|köşesinde|kulisi)\b", re.IGNORECASE),
)

_FIRST_PERSON_MARKERS_RAW: Final[tuple[str, ...]] = (
    "bence",
    "bana göre",
    "kanımca",
    "benim gördüğüm",
    "şahsen",
    "yazımda",
    "köşemde",
    "düşünüyorum",
    "inanıyorum",
)
_FIRST_PERSON_MARKERS: Final[tuple[str, ...]] = tuple(
    dict.fromkeys(fold_text(m) for m in _FIRST_PERSON_MARKERS_RAW)
)


@dataclass(frozen=True)
class ContentClassification:
    is_opinion: bool
    confidence: float
    reasons: tuple[str, ...]
    content_kind: str  # "news" | "opinion_column" | "analysis"


def classify_content_kind(
    title: str,
    text: str = "",
    author: str | None = None,
    section: str | None = None,
) -> ContentClassification:
    """Metnin haber mi, köşe yazısı mı olduğunu analiz eder."""
    reasons: list[str] = []
    title_folded = fold_text(title)
    text_folded = fold_text(text[:1000])  # İlk 1000 karakter

    # 1. Bölüm / kategori sinyali
    if section:
        s_folded = fold_text(section)
        if any(h in s_folded for h in _OPINION_COLUMN_HINTS):
            reasons.append(f"Kategori sinyali: '{section}'")

    # 2. Başlık kalıpları
    if any(h in title_folded for h in _OPINION_COLUMN_HINTS):
        reasons.append("Başlıkta köşe/kulis/yorum ifadesi var")

    for pat in _OPINION_TITLE_PATTERNS:
        if pat.search(title):
            reasons.append(f"Başlık kalıbı eşleşti: {pat.pattern}")

    # 3. Yazar alanı dolu ve metinde birinci tekil şahıs dili
    first_person_hits = [m for m in _FIRST_PERSON_MARKERS if m in text_folded]
    if author and first_person_hits:
        reasons.append(f"Yazar belirtilmiş ve birinci şahıs dili var: {first_person_hits[:2]}")

    is_opinion = len(reasons) > 0
    kind = "opinion_column" if is_opinion else "news"
    score = min(1.0, len(reasons) * 0.4) if is_opinion else 0.0

    return ContentClassification(
        is_opinion=is_opinion,
        confidence=score,
        reasons=tuple(reasons),
        content_kind=kind,
    )
