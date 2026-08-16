"""Bağımsız kanıt sayımı (F2-11, Spec §8.2).

DoD: Ajans kopyası, yayın grubu ve kopyala-yapıştır grupları tek sayılıyor.

> "10 kaynak yazdı" ≠ "10 bağımsız teyit."

`ingestion/independence.py` bu işin **iskeletiydi** (F1-11): yalnızca ilk iki
kuralı uyguluyordu ve amacı tekilleştirme sırasında bir grup anahtarı
üretmekti. Bu modül Spec §8.2'nin **tamamını** uygular ve kanıt motorunun
parçasıdır.

Eklenen: **3. kural — kopyala-yapıştır tespiti.**

```
EĞER cosine(e.article.embedding, diger.embedding) >= 0.95
     VE ortak_ngram_orani >= 0.60:
    DÖN "dup:" + min(id'ler)
```

İki koşulun **birlikte** aranması Spec'in kendi tasarımıdır ve Faz 1'in
ölçümüyle doğrulanmıştır: kısa metinlerde simhash tek başına yetmiyordu
(40 kelimelik bir TCMB metnine eklenen tek cümle simhash'i 9 bit kaydırdı,
eşik 6). Embedding benzerliği anlamı, n-gram içermesi *ifadeyi* yakalar;
kopyala-yapıştır ikisini birden tetikler, bağımsız iki haber tetiklemez.

⛔ Bu modül `politikdesk.llm` import EDEMEZ (Spec §11.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from politikdesk.ingestion.dedup import (
    MIN_TOKENS_FOR_NGRAM,
    NGRAM_CONTAINMENT_THRESHOLD,
    containment,
    hamming_distance,
    ngram_set,
)

WIRE_COPY_MAX_DISTANCE = 6  # Spec §8.2 kural 2
DUP_COSINE_THRESHOLD = 0.95  # Spec §8.2 kural 3
DUP_NGRAM_THRESHOLD = NGRAM_CONTAINMENT_THRESHOLD

# Spec §9.1 — kaynak katmanı ile `kind` eşlemesi
KIND_BY_TIER = {1: "official", 2: "wire", 3: "media", 4: "social"}


@dataclass(frozen=True)
class EvidenceArticle:
    """Bağımsızlık çözümlemesi için gereken makale bilgisi.

    `text`: n-gram karşılaştırması için başlık + alıntı (tam metin
    saklanmıyor — Spec §9.3).
    """

    article_id: int
    source_slug: str
    tier: int
    kind: str  # official | wire | media | social
    independence_group: str | None = None
    simhash: int = 0
    embedding: list[float] = field(default_factory=list)
    text: str = ""

    @property
    def is_wire(self) -> bool:
        return self.kind == "wire"


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def is_copy_paste(a: EvidenceArticle, b: EvidenceArticle) -> bool:
    """Spec §8.2 kural 3: gövde benzerliği çok yüksek + n-gram örtüşmesi.

    İki koşul da aranır. Yalnız embedding'e bakmak, aynı olayı anlatan iki
    bağımsız haberi kopya sayardı — bağımsız kanıt sayımını sistematik
    olarak DÜŞÜRÜRDÜ ve her şey 🟠 single_source'a doğru kayardı.
    """
    if _cosine(a.embedding, b.embedding) < DUP_COSINE_THRESHOLD:
        return False

    set_a, set_b = ngram_set(a.text), ngram_set(b.text)
    if len(set_a) < MIN_TOKENS_FOR_NGRAM or len(set_b) < MIN_TOKENS_FOR_NGRAM:
        # Metin n-gram için çok kısa; tek sinyalle kopya ilan edilmez.
        return False
    return containment(set_a, set_b) >= DUP_NGRAM_THRESHOLD


def _own_key(article: EvidenceArticle) -> str:
    """Bir makalenin KENDİ anahtarı — kopya ilişkisine bakmadan.

    Yayın grubu her zaman önceliklidir (Spec §8.2 kural 1). Ajans için de
    geçerlidir: ajansın anahtarı `wire:<slug>` olarak sabitlenirse, aynı
    gruba ait bir kopya `grp:<grup>` anahtarına düşer ve ikisi AYRI
    sayılır — bağımsız sayım şişer.

    > Bu, Faz 1'de yakalanan hatanın **ikinci biçimidir.** Faz 1'de kopya
    > simhash ile tespit ediliyordu ve `wire:<slug>` çözümü işe yarıyordu;
    > kopya yayın grubuyla eşleştiğinde aynı çözüm hatayı geri getiriyordu.
    > F2-16 eval koşucusu bunu `gc-024` üzerinde yakaladı.
    """
    if article.independence_group:
        return f"grp:{article.independence_group}"
    if article.is_wire:
        return f"wire:{article.source_slug}"
    return f"src:{article.source_slug}"


def merge_key(
    article: EvidenceArticle,
    *,
    others: list[EvidenceArticle] | None = None,
    max_distance: int = WIRE_COPY_MAX_DISTANCE,
) -> str:
    """Spec §8.2 `birlestirme_anahtari` — dört kural, sırayla."""
    others = others or []

    # 1) Aynı yayın grubu / ajans zinciri — ajans dahil herkes için.
    if article.independence_group:
        return _own_key(article)

    # Ajansın grubu yoksa kendi slug'ı grup görevi görür; kopyaları da
    # aşağıda bu anahtara yönlendirilir.
    if article.is_wire:
        return _own_key(article)

    # 2) Ajans kopyası: simhash yakınlığı -> AJANSIN KENDİ anahtarı.
    # `wire:<slug>` sabiti yerine ajansın gerçek anahtarı kullanılır;
    # aksi halde ajansın grubu varsa ikisi yine ayrışır.
    for other in others:
        if other.article_id == article.article_id or not other.is_wire:
            continue
        if (
            article.simhash
            and other.simhash
            and hamming_distance(article.simhash, other.simhash) <= max_distance
        ):
            return _own_key(other)

    # 3) Kopyala-yapıştır: embedding + n-gram
    for other in others:
        if other.article_id == article.article_id:
            continue
        if is_copy_paste(article, other):
            return f"dup:{min(article.article_id, other.article_id)}"

    # 4) Bağımsız
    return _own_key(article)


def group_by_independence(
    articles: list[EvidenceArticle], *, max_distance: int = WIRE_COPY_MAX_DISTANCE
) -> dict[str, list[EvidenceArticle]]:
    """Makaleleri bağımsızlık anahtarına göre gruplar."""
    groups: dict[str, list[EvidenceArticle]] = {}
    for article in articles:
        key = merge_key(article, others=articles, max_distance=max_distance)
        groups.setdefault(key, []).append(article)
    return groups


def independent_count(
    articles: list[EvidenceArticle], *, max_distance: int = WIRE_COPY_MAX_DISTANCE
) -> int:
    """Spec §8.2 `bagimsiz_sayim` — R2/R4/R5'in girdisi."""
    return len(group_by_independence(articles, max_distance=max_distance))


def breakdown_by_kind(
    articles: list[EvidenceArticle], *, max_distance: int = WIRE_COPY_MAX_DISTANCE
) -> dict[str, int]:
    """UI kırılımı (Spec §8.2): "Resmî: 1 · Ajans: 1 · Bağımsız medya: 3".

    **Tek bir toplam sayı gösterilmez** — kırılım zorunludur. Bir grup,
    içindeki en güçlü katmanla temsil edilir.
    """
    counts = {"official": 0, "wire": 0, "media": 0, "social": 0}
    for group in group_by_independence(articles, max_distance=max_distance).values():
        kinds = {a.kind for a in group}
        for kind in ("official", "wire", "media", "social"):
            if kind in kinds:
                counts[kind] += 1
                break
    return counts


def has_primary_source(articles: list[EvidenceArticle]) -> bool:
    """Spec §8.3 R2: Tier 1 kaynakta destekleyen kanıt var mı?

    Çağıran, listeyi yalnızca `stance='supports'` kanıtlarla vermelidir.
    """
    return any(a.tier == 1 for a in articles)
