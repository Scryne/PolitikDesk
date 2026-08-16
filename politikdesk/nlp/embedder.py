"""Embedding üretimi (F1-13).

DoD: Yeni her makale 60 sn içinde embed ediliyor; hata durumunda kuyruğa
geri alınıyor.

Sağlayıcı seçimi D16'ya bağlıdır (`docs/embedding-benchmark.md`). Bu modül
sağlayıcı-agnostiktir: `PD_EMBEDDING_PROVIDER` ayarı hangi arka ucun
kullanılacağını belirler.

`hashing` sağlayıcısı: API anahtarı olmadan boru hattını uçtan uca
koşturmak için deterministik bir yerel embedder. **Üretimde kullanılmaz** —
`is_production_ready = False` ile işaretlidir ve sağlık paneli bunu gösterir.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from typing import Protocol, cast

from politikdesk.config import Settings, get_settings
from politikdesk.ingestion.dedup import tokenize
from politikdesk.observability import get_logger

log = get_logger(__name__)

EMBEDDING_DIM = 1024  # migrations/0001_initial.sql VECTOR(1024)


class EmbeddingBackend(Protocol):
    name: str
    is_production_ready: bool

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbedder:
    """Deterministik yerel embedder — geliştirme ve test için.

    Token'ları sabit boyutlu bir vektöre hash'ler (hashing trick) ve
    L2 normalize eder. Semantik yakınlık yakalamaz; yalnızca sözcük
    örtüşmesini yansıtır. Kümeleme kalitesi için YETERSİZDİR.

    Var olma sebebi: F1-13'ün "her makale embed ediliyor" akışının,
    D16 kararı verilmeden ve API anahtarı olmadan test edilebilmesi.
    """

    name = "hashing"
    is_production_ready = False

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        tokens = tokenize(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dim
            sign = 1.0 if (value >> 63) & 1 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return vector
        return [v / norm for v in vector]


class VoyageEmbedder:
    name = "voyage"
    is_production_ready = True

    def __init__(self, model: str) -> None:
        import voyageai

        self.client = voyageai.Client()
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embed(texts, model=self.model, input_type="document")
        return cast("list[list[float]]", response.embeddings)


class CohereEmbedder:
    name = "cohere"
    is_production_ready = True

    def __init__(self, model: str) -> None:
        import cohere

        self.client = cohere.ClientV2()
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embed(
            texts=texts,
            model=self.model,
            input_type="search_document",
            embedding_types=["float"],
        )
        return response.embeddings.float_


class OpenAIEmbedder:
    name = "openai"
    is_production_ready = True

    def __init__(self, model: str, dim: int = EMBEDDING_DIM) -> None:
        from openai import OpenAI

        self.client = OpenAI()
        self.model = model
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(input=texts, model=self.model, dimensions=self.dim)
        return [d.embedding for d in response.data]


# Bazı self-host modelleri girdi öneki ZORUNLU kılar (model kartı kuralı).
# Öneksiz kullanım ayrım gücünü düşürür ve benchmark'ta ölçülen kaliteyi
# üretimde vermez. D16 benchmark'ı e5 için `query: ` önekiyle koşuldu
# (docs/embedding-benchmark.md); üretim aynı öneki uygulamak ZORUNDADIR.
MODEL_TEXT_PREFIXES: dict[str, str] = {
    "intfloat/multilingual-e5-large": "query: ",
    "intfloat/multilingual-e5-base": "query: ",
    "intfloat/multilingual-e5-small": "query: ",
}


def text_prefix_for(model: str) -> str:
    return MODEL_TEXT_PREFIXES.get(model.strip(), "")


class LocalEmbedder:
    """Self-host embedder (D16: multilingual-e5-large).

    `normalize_embeddings=True`: pgvector kosinüs mesafesi normalize
    edilmemiş vektörlerle de doğru çalışır, ama HNSW indeksinin davranışı
    tutarlı olsun diye makale vektörleri birim uzunlukta tutulur. Olay
    merkezi bunun **ortalamasıdır** ve normalize edilmez — bkz.
    `clustering/centroid.py`.
    """

    name = "local"
    is_production_ready = True

    def __init__(self, model: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model)
        self.prefix = text_prefix_for(model)
        if self.prefix:
            log.info("embedding_prefix_applied", model=model, prefix=self.prefix)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.prefix:
            texts = [self.prefix + t for t in texts]
        return [v.tolist() for v in self.model.encode(texts, normalize_embeddings=True)]


def build_backend(settings: Settings | None = None) -> EmbeddingBackend:
    """Ayarlara göre embedding arka ucunu kurar."""
    settings = settings or get_settings()
    provider = (settings.embedding_provider or "").strip().lower()

    if not provider or provider == "hashing":
        log.warning(
            "embedding_backend_not_production",
            hint="PD_EMBEDDING_PROVIDER ayarlı değil; yerel hashing embedder "
            "kullanılıyor. Kümeleme kalitesi için D16 kararı gerekir "
            "(docs/embedding-benchmark.md).",
        )
        return HashingEmbedder(settings.embedding_dim)

    model = settings.embedding_model
    if not model:
        raise ValueError(f"PD_EMBEDDING_MODEL ayarlanmalı (provider={provider})")

    backends: dict[str, Callable[[], EmbeddingBackend]] = {
        "voyage": lambda: VoyageEmbedder(model),
        "cohere": lambda: CohereEmbedder(model),
        "openai": lambda: OpenAIEmbedder(model, settings.embedding_dim),
        "local": lambda: LocalEmbedder(model),
    }
    try:
        return backends[provider]()
    except KeyError as exc:
        raise ValueError(
            f"Bilinmeyen embedding sağlayıcısı: {provider!r}. "
            f"Seçenekler: {sorted(backends)} veya 'hashing'"
        ) from exc


def embedding_text(title: str, excerpt: str | None) -> str:
    """Embed edilecek metni kurar.

    Başlık + alıntı. Bu biçim `eval/pairs_tr.jsonl` ile **aynı olmalıdır** —
    aksi halde benchmark üretimi yansıtmaz (bkz. eval/README.md).
    """
    parts = [title.strip()]
    if excerpt:
        parts.append(excerpt.strip())
    return " ".join(p for p in parts if p)


def to_pgvector(vector: list[float]) -> str:
    """pgvector'ün beklediği metin biçimi: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{v:.6f}" for v in vector) + "]"
