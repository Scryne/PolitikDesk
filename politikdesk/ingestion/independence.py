"""Bağımsızlık grubu çözümlemesi (F1-11 iskeleti → F2-11 tam sürüm).

Spec §8.2: "10 kaynak yazdı" ≠ "10 bağımsız teyit".

Bu modül, bir makalenin **birleştirme anahtarını** üretir. Aynı anahtara
düşen makaleler bağımsız sayımda TEK sayılır.

Anahtar önceliği (Spec §8.2 `birlestirme_anahtari`):
    1. grp:<independence_group>   aynı yayın grubu / ajans zinciri
    2. wire:<ajans_slug>          ajans kopyası (simhash yakınlığı)
    3. dup:<id>                   kopyala-yapıştır (gövde benzerliği)
    4. src:<kaynak_slug>          bağımsız

⚠️ Bu modül `evidence/` altında DEĞİL, `ingestion/` altındadır: burada
üretilen yalnızca gruplama anahtarıdır, kanıt DURUMU değil. Durum
hesabı (R0–R7) Faz 2'de `evidence/rules.py` içinde ve deterministik
olarak yapılır.
"""

from __future__ import annotations

from dataclasses import dataclass

from politikdesk.ingestion.dedup import hamming_distance

WIRE_COPY_MAX_DISTANCE = 6


@dataclass(frozen=True)
class ArticleFingerprint:
    """Bağımsızlık çözümlemesi için gereken asgari makale bilgisi."""

    article_id: int
    source_slug: str
    independence_group: str | None
    kind: str  # official | wire | media | social
    simhash: int


def is_wire(fingerprint: ArticleFingerprint) -> bool:
    return fingerprint.kind == "wire"


def independence_key(
    article: ArticleFingerprint,
    *,
    wire_articles: list[ArticleFingerprint] | None = None,
    max_distance: int = WIRE_COPY_MAX_DISTANCE,
) -> str:
    """Bir makalenin bağımsızlık anahtarını üretir.

    `wire_articles`: aynı olaydaki ajans makaleleri. Bir medya makalesi
    bunlardan birine simhash olarak yakınsa, o ajansın grubuna düşer —
    kopyaladığı için bağımsız teyit sayılmaz.
    """
    # Ajansın kendi anahtarı `wire:<slug>` olmalıdır — aksi halde kopyası
    # `wire:aa-ekonomi`, kendisi `grp:wire-aa` anahtarına düşer ve ikisi
    # AYRI sayılır. Bu, bağımsız kanıt sayımını sistematik olarak şişirir.
    if is_wire(article):
        return f"wire:{article.source_slug}"

    base = (
        f"grp:{article.independence_group}"
        if article.independence_group
        else f"src:{article.source_slug}"
    )

    if not wire_articles or not article.simhash:
        return base

    for wire in wire_articles:
        if wire.article_id == article.article_id or not wire.simhash:
            continue
        if hamming_distance(article.simhash, wire.simhash) <= max_distance:
            return f"wire:{wire.source_slug}"

    return base


def count_independent(
    articles: list[ArticleFingerprint], *, max_distance: int = WIRE_COPY_MAX_DISTANCE
) -> int:
    """Bağımsız kaynak sayısı (Spec §8.2 `bagimsiz_sayim`)."""
    return len(group_by_independence(articles, max_distance=max_distance))


def group_by_independence(
    articles: list[ArticleFingerprint], *, max_distance: int = WIRE_COPY_MAX_DISTANCE
) -> dict[str, list[ArticleFingerprint]]:
    """Makaleleri bağımsızlık anahtarına göre gruplar."""
    wires = [a for a in articles if is_wire(a)]
    groups: dict[str, list[ArticleFingerprint]] = {}
    for article in articles:
        key = independence_key(article, wire_articles=wires, max_distance=max_distance)
        groups.setdefault(key, []).append(article)
    return groups


def breakdown_by_kind(articles: list[ArticleFingerprint]) -> dict[str, int]:
    """UI'da gösterilen kırılım (Spec §8.2).

    "Resmî: 1 · Ajans: 1 · Bağımsız medya: 3 · Sosyal: 4"
    Tek bir toplam sayı GÖSTERİLMEZ — kırılım zorunludur.
    """
    counts = {"official": 0, "wire": 0, "media": 0, "social": 0}
    for group in group_by_independence(articles).values():
        # Grup içindeki en güçlü katman grubu temsil eder.
        kinds = [a.kind for a in group]
        for kind in ("official", "wire", "media", "social"):
            if kind in kinds:
                counts[kind] += 1
                break
    return counts
