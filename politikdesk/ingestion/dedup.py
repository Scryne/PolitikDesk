"""Tekilleştirme — tam tekrar ve yakın tekrar (F1-10, F1-11).

F1-10 DoD: aynı içerik iki kez gelirse ikinci kayıt oluşmuyor.
F1-11 DoD: Hamming mesafesi ≤6 olan makaleler işaretleniyor; AA haberini
kopyalayan siteler tespit ediliyor.

**Neden bu modül kritik:** Spec §8.2'deki bağımsız kanıt sayımı buna
dayanır. "10 kaynak yazdı" ≠ "10 bağımsız teyit". Ajans kopyası tespiti
yanlışsa kanıt motoru sistematik olarak yanılır (Risk: F1-11, en yüksek
riskli 5 görevden biri).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

# Spec §8.2: simhash Hamming mesafesi <= 6 -> yakın tekrar / ajans kopyası
SIMHASH_BITS = 64
NEAR_DUPLICATE_MAX_DISTANCE = 6

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

# Türkçe durak kelimeler: parmak izini içerikten çok dilbilgisinden
# etkilenmekten korur.
_STOPWORDS = frozenset(
    {
        "ve",
        "ile",
        "bir",
        "bu",
        "da",
        "de",
        "için",
        "olarak",
        "olan",
        "daha",
        "en",
        "gibi",
        "ancak",
        "ise",
        "ki",
        "mi",
        "mu",
        "ya",
        "veya",
        "her",
        "çok",
        "sonra",
        "önce",
        "kadar",
        "göre",
        "üzere",
        "the",
        "of",
        "in",
    }
)


def tokenize(text: str) -> list[str]:
    """Metni parmak izi için token'lara ayırır.

    Türkçe'ye özgü not: `casefold()` yerine `lower()` kullanılamaz —
    'I' harfi Türkçe'de 'ı'ya dönüşmelidir ve Python'un varsayılan
    `lower()`'ı locale bağımsızdır. NFC normalizasyonu birleşik/ayrık
    kodlanmış karakterleri eşitler.
    """
    normalized = unicodedata.normalize("NFC", text)
    # Türkçe büyük İ -> i, I -> ı eşlemesi
    normalized = normalized.replace("İ", "i").replace("I", "ı")
    tokens = _TOKEN_RE.findall(normalized.casefold())
    return [t for t in tokens if len(t) > 2 and t not in _STOPWORDS]


def _shingles(tokens: list[str], size: int = 2) -> list[str]:
    """Bitişik kelime ikilileri. Tek kelimeye göre kopyalamayı daha iyi ayırır."""
    if len(tokens) < size:
        return tokens
    return [" ".join(tokens[i : i + size]) for i in range(len(tokens) - size + 1)]


def compute_simhash(text: str, bits: int = SIMHASH_BITS) -> int:
    """Charikar simhash — yakın tekrar tespiti için (F1-11)."""
    tokens = tokenize(text)
    if not tokens:
        return 0

    features = _shingles(tokens) + tokens
    vector = [0] * bits

    for feature in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        for i in range(bits):
            if value >> i & 1:
                vector[i] += 1
            else:
                vector[i] -= 1

    result = 0
    for i in range(bits):
        if vector[i] > 0:
            result |= 1 << i
    return result


def hamming_distance(a: int, b: int) -> int:
    """İki simhash arasındaki bit farkı."""
    return ((a ^ b) & ((1 << SIMHASH_BITS) - 1)).bit_count()


# --------------------------------------------------------------------------
# N-gram örtüşmesi — Spec §8.2 `ortak_ngram_orani >= 0.60`
#
# NEDEN İKİNCİ SİNYAL GEREKLİ: simhash, uzun web belgeleri için tasarlanmıştır.
# Bizim sakladığımız metin kısadır (başlık + ≤300 karakter alıntı). Kopyalayan
# site metnin sonuna tek bir cümle eklediğinde bile bit farkı 6'yı aşabilir —
# ölçüldü: 40 kelimelik bir metne 3 kelime eklemek 9 bit kaydırıyor.
#
# Bu yüzden Spec §8.2'nin ikinci ölçütü (ortak n-gram oranı) uygulanır.
# İçerme (containment) oranı, bir tarafın diğerinden uzun olmasına karşı
# dayanıklıdır — kopyala-yapıştır tam olarak bu biçimde görünür.
# --------------------------------------------------------------------------
NGRAM_SIZE = 3
NGRAM_CONTAINMENT_THRESHOLD = 0.60
MIN_TOKENS_FOR_NGRAM = 8


@lru_cache(maxsize=8192)
def ngram_set(text: str, size: int = NGRAM_SIZE) -> frozenset[str]:
    tokens = tokenize(text)
    if len(tokens) < size:
        return frozenset(tokens)
    return frozenset(" ".join(tokens[i : i + size]) for i in range(len(tokens) - size + 1))


def containment(a: frozenset[str], b: frozenset[str]) -> float:
    """Küçük olanın ne kadarı büyüğün içinde? (overlap coefficient)"""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def is_near_duplicate(
    a: int,
    b: int,
    max_distance: int = NEAR_DUPLICATE_MAX_DISTANCE,
    *,
    text_a: str | None = None,
    text_b: str | None = None,
) -> bool:
    """Yakın tekrar mı? (Spec §8.2)

    İki sinyalden biri yeterlidir:
      1. simhash Hamming mesafesi <= 6           (hızlı, kaba)
      2. ortak n-gram içerme oranı >= 0.60       (kısa metinde güvenilir)
    """
    if a and b and hamming_distance(a, b) <= max_distance:
        return True

    if text_a and text_b:
        set_a, set_b = ngram_set(text_a), ngram_set(text_b)
        if len(set_a) >= MIN_TOKENS_FOR_NGRAM and len(set_b) >= MIN_TOKENS_FOR_NGRAM:
            return containment(set_a, set_b) >= NGRAM_CONTAINMENT_THRESHOLD

    return False


@dataclass(frozen=True)
class DuplicateVerdict:
    """Bir makalenin tekrar durumu."""

    kind: str  # "new" | "exact" | "near"
    matched_article_id: int | None = None
    distance: int | None = None

    @property
    def should_store(self) -> bool:
        """Tam tekrar saklanmaz. Yakın tekrar SAKLANIR ama işaretlenir.

        Gerekçe: ajans kopyası ayrı bir yayındır ve kaynak karşılaştırma
        tablosunda görünmelidir — ancak bağımsız kanıt sayımında tek
        sayılmalıdır (Spec §8.2).
        """
        return self.kind != "exact"


def classify(
    content_hash: str,
    simhash: int,
    *,
    existing_hashes: dict[str, int],
    existing_simhashes: list[tuple[int, int]],
    max_distance: int = NEAR_DUPLICATE_MAX_DISTANCE,
    text: str | None = None,
    existing_texts: dict[int, str] | None = None,
) -> DuplicateVerdict:
    """Yeni bir makalenin tekrar durumunu belirler.

    `existing_hashes`     : content_hash -> article_id
    `existing_simhashes`  : (article_id, simhash) listesi
    `text` / `existing_texts` : verilirse n-gram içerme ölçütü de uygulanır
                                (Spec §8.2 ikinci sinyal)
    """
    matched = existing_hashes.get(content_hash)
    if matched is not None:
        return DuplicateVerdict(kind="exact", matched_article_id=matched, distance=0)

    best: tuple[int, int] | None = None

    if simhash:
        for article_id, other_simhash in existing_simhashes:
            if not other_simhash:
                continue
            distance = hamming_distance(simhash, other_simhash)
            if distance <= max_distance and (best is None or distance < best[1]):
                best = (article_id, distance)

    if best is not None:
        return DuplicateVerdict(kind="near", matched_article_id=best[0], distance=best[1])

    # İkinci sinyal: n-gram içermesi (Spec §8.2). simhash kaçırdığında devreye
    # girer — kopyalayan site metne kendi cümlesini eklediğinde tipik durum.
    if text and existing_texts:
        candidate = ngram_set(text)
        if len(candidate) >= MIN_TOKENS_FOR_NGRAM:
            for article_id, other_text in existing_texts.items():
                other_ngrams = ngram_set(other_text)
                if len(other_ngrams) < MIN_TOKENS_FOR_NGRAM:
                    continue
                if containment(candidate, other_ngrams) >= NGRAM_CONTAINMENT_THRESHOLD:
                    return DuplicateVerdict(
                        kind="near", matched_article_id=article_id, distance=None
                    )

    return DuplicateVerdict(kind="new")
