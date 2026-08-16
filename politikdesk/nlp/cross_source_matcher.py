"""B-81 — Çapraz Kaynak İddia Eşleştirme Motoru (Cross-Source Claim Matching).

Bu modül, farklı yayın organları ve kaynaklardan gelen haberlerde aynı olgusal
veya sayısal iddiaların farklı sözcüklerle ifade edildiği durumları semantik,
sayısal ve varlık bazlı olarak eşleştirir.
"""

from __future__ import annotations

import re
from typing import Any

from politikdesk.nlp.claims import ExtractedClaim, fold_text

TURKISH_STOPWORDS: frozenset[str] = frozenset(
    {
        "ve",
        "veya",
        "ile",
        "de",
        "da",
        "ki",
        "bir",
        "bu",
        "su",
        "o",
        "icin",
        "olarak",
        "gore",
        "tarafindan",
        "dair",
        "gibi",
        "kadar",
        "olan",
        "oldugu",
        "etti",
        "ettigini",
        "acikladi",
        "bildirdi",
        "duyurdu",
        "belirtti",
        "aktardi",
        "soyledi",
        "yapti",
        "oldu",
        "ise",
        "daha",
        "en",
        "cok",
        "az",
        "sonra",
        "once",
        "ayni",
        "seviyesinde",
        "duzeyinde",
        "oraninda",
    }
)

INSTITUTION_ALIASES: dict[str, str] = {
    "merkez bankasi": "tcmb",
    "turkiye cumhuriyet merkez bankasi": "tcmb",
    "para politikasi kurulu": "ppk",
    "turkiye istatistik kurumu": "tuik",
    "gelir idaresi baskanligi": "gib",
    "hazine ve maliye bakanligi": "hazine",
}

_NEGATION_WORDS: frozenset[str] = frozenset(
    {
        "degil",
        "yok",
        "olmadi",
        "gerceklesmedi",
        "artmadi",
        "azalmadi",
        "dusmedi",
    }
)

_COMMON_SUFFIXES: tuple[str, ...] = (
    "lerden",
    "lardan",
    "lerine",
    "larina",
    "lerinde",
    "larinda",
    "lerini",
    "larini",
    "lerin",
    "larin",
    "lerle",
    "larla",
    "sinden",
    "sindan",
    "sinde",
    "sinda",
    "sini",
    "sina",
    "sine",
    "inden",
    "indan",
    "unden",
    "inde",
    "inda",
    "unde",
    "unda",
    "leri",
    "lari",
    "lerle",
    "larla",
    "den",
    "dan",
    "ten",
    "tan",
    "nin",
    "nun",
    "nun",
    "in",
    "un",
    "ye",
    "ya",
    "ne",
    "na",
    "de",
    "da",
    "te",
    "ta",
    "yi",
    "yu",
    "i",
    "u",
    "si",
    "su",
    "ce",
    "ca",
)


def _stem_turkish(word: str) -> str:
    if len(word) <= 3:
        return word
    for suff in _COMMON_SUFFIXES:
        if word.endswith(suff) and len(word) - len(suff) >= 3:
            return word[: -len(suff)]
    return word


def _extract_content_tokens(text: str) -> set[str]:
    normalized = fold_text(text)
    for alias, standard in INSTITUTION_ALIASES.items():
        normalized = normalized.replace(alias, standard)

    raw_tokens = re.findall(r"\w+", normalized)
    tokens: set[str] = set()
    for t in raw_tokens:
        if t in TURKISH_STOPWORDS:
            continue
        stemmed = _stem_turkish(t)
        if len(stemmed) >= 2 and stemmed not in TURKISH_STOPWORDS:
            tokens.add(stemmed)
    return tokens


def _has_negation(text: str) -> bool:
    tokens = set(re.findall(r"\w+", fold_text(text)))
    if tokens & _NEGATION_WORDS:
        return True
    return any(t.endswith(("madi", "medi", "madi", "medi", "maz", "mez")) for t in tokens)


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def are_claims_equivalent(c1: ExtractedClaim, c2: ExtractedClaim) -> bool:
    if c1.claim_type != c2.claim_type:
        return False

    # 1. Sayısal iddialar
    if c1.claim_type == "number":
        v1 = c1.normalized_value or {}
        v2 = c2.normalized_value or {}
        if not v1 or not v2:
            return False
        return (
            v1.get("metric") == v2.get("metric")
            and v1.get("value") == v2.get("value")
            and v1.get("period") == v2.get("period")
        )

    # 2. Olumsuzluk tutarlılığı
    if _has_negation(c1.claim_text) != _has_negation(c2.claim_text):
        return False

    # 3. İçerik sözcükleri benzerliği
    tokens1 = _extract_content_tokens(c1.claim_text)
    tokens2 = _extract_content_tokens(c2.claim_text)

    sim = jaccard_similarity(tokens1, tokens2)
    common = tokens1 & tokens2

    if len(common) >= 2 and sim >= 0.35:
        return True
    return sim >= 0.45


def match_and_group_claims(
    collected: list[tuple[ExtractedClaim, int]],
) -> list[tuple[ExtractedClaim, list[tuple[int, str]]]]:
    groups: list[dict[str, Any]] = []

    for claim, article_id in collected:
        matched_group = None
        for g in groups:
            rep_claim = g["representative"]
            if are_claims_equivalent(rep_claim, claim):
                matched_group = g
                break

        if matched_group is not None:
            sources: list[tuple[int, str]] = matched_group["sources"]
            if not any(aid == article_id for aid, _ in sources):
                sources.append((article_id, claim.quote_span))
        else:
            groups.append(
                {
                    "representative": claim,
                    "sources": [(article_id, claim.quote_span)],
                }
            )

    return [(g["representative"], g["sources"]) for g in groups]
