"""Ingestion veri tipleri.

`RawItem`, adaptörlerin ürettiği ham birimdir. Normalizasyondan önceki
tek temas noktasıdır — adaptörler DB'ye yazmaz, yalnızca RawItem üretir.
Bu ayrım, sahte (fake) adaptörle test yazmayı mümkün kılar (F1-01 DoD).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class RawItem:
    """Bir kaynaktan çekilmiş, henüz normalize edilmemiş yayın birimi."""

    source_slug: str
    url: str
    title: str
    published_at: datetime | None = None
    summary: str | None = None
    """Kaynağın kendi verdiği özet/açıklama. TAM METİN DEĞİLDİR."""
    guid: str | None = None
    lang: str = "tr"
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.url:
            raise ValueError("RawItem.url boş olamaz")
        if not self.title:
            raise ValueError("RawItem.title boş olamaz")


@dataclass(frozen=True, slots=True)
class NormalizedArticle:
    """Normalize edilmiş, saklamaya hazır makale.

    Spec §9.3 saklama politikası burada uygulanmıştır:
      excerpt        <= 300 karakter, süresiz
      lead_paragraph işleme amaçlı, raw_purge_at ile silinir
      tam metin      YOK
    """

    source_slug: str
    canonical_url: str
    title: str
    excerpt: str | None
    lead_paragraph: str | None
    published_at: datetime | None
    content_hash: str
    simhash: int
    lang: str
    raw_purge_at: datetime
    topics: tuple[str, ...] = ()
    official_value: dict[str, Any] | None = None
    """Kaynağın KENDİ makine okunur yayınından gelen sayı (F5-19).

    Modelden değil kurumdan gelir; yalnızca resmî veri servisi olan
    adaptörler doldurur (şu an `tuik_sdmx`). Kanıt motoru bunu iddianın
    `normalized_value`'si ile karşılaştırıp Spec §8.3 R3'ün
    `verified_against_source` bayrağını belirler.
    """


@dataclass(slots=True)
class FetchResult:
    """Bir kaynaktan tek bir çekim turunun sonucu (sağlık paneli girdisi)."""

    source_slug: str
    items: list[RawItem] = field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass(slots=True)
class IngestionStats:
    """Boru hattının bir turdaki sonucu."""

    fetched: int = 0
    stored: int = 0
    exact_duplicates: int = 0
    near_duplicates: int = 0
    filtered_out: int = 0
    errors: int = 0

    def merge(self, other: IngestionStats) -> None:
        self.fetched += other.fetched
        self.stored += other.stored
        self.exact_duplicates += other.exact_duplicates
        self.near_duplicates += other.near_duplicates
        self.filtered_out += other.filtered_out
        self.errors += other.errors
