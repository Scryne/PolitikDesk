"""Embedding modeli benchmark koşucusu (F0-13, D16).

Amaç: Türkçe haber çiftlerinde "aynı olay / farklı olay" ayrım gücünü
ölçmek ve kümeleme eşiği (T_HIGH/T_LOW) için başlangıç önerisi çıkarmak.

DoD (F0-13):
  * en az 3 aday model
  * 60 Türkçe haber çifti (30 aynı olay / 30 farklı olay)
  * ayrım gücü: ROC-AUC + eşik önerisi
  * 1024 boyut uyumu doğrulanmış
  * maliyet karşılaştırması

Girdi biçimi (eval/pairs_tr.jsonl, satır başına bir JSON nesnesi):
    {"id": "p001", "a": "başlık + lead metni", "b": "...", "same_event": true,
     "difficulty": "easy|hard", "note": "opsiyonel"}

Kullanım:
    python -m eval.embedding_benchmark --list-candidates
    python -m eval.embedding_benchmark --pairs eval/pairs_tr.jsonl \\
        --candidates voyage-3,cohere-multilingual-3,e5-large
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_DIM = 1024  # migrations/0001_initial.sql VECTOR(1024)


# ---------------------------------------------------------------- veri tipleri
@dataclass(frozen=True)
class Pair:
    id: str
    a: str
    b: str
    same_event: bool
    difficulty: str = "easy"
    note: str = ""


@dataclass(frozen=True)
class Candidate:
    """Bir aday embedding modeli."""

    key: str
    provider: str
    model: str
    dim: int
    usd_per_million_tokens: float
    self_hosted: bool = False
    notes: str = ""
    # Bazı self-host modelleri girdi öneki ZORUNLU kılar (model kartı kuralı).
    # multilingual-e5 ailesi öneksiz kullanıldığında ayrım gücü düşer; öneki
    # uygulamamak modeli haksız yere elemek olur. Üretimde de aynı önek
    # uygulanır (politikdesk/nlp/embedder.py).
    text_prefix: str = ""


# Aday listesi. Fiyat/boyut bilgileri koşumdan önce sağlayıcı sayfasından
# teyit edilmeli; benchmark raporuna teyit tarihi yazılır.
CANDIDATES: dict[str, Candidate] = {
    "voyage-3": Candidate(
        key="voyage-3",
        provider="voyage",
        model="voyage-3",
        dim=1024,
        usd_per_million_tokens=0.06,
        notes="Barındırılan, çok dilli. 1024 doğal boyut.",
    ),
    "cohere-multilingual-3": Candidate(
        key="cohere-multilingual-3",
        provider="cohere",
        model="embed-multilingual-v3.0",
        dim=1024,
        usd_per_million_tokens=0.10,
        notes="Barındırılan, çok dilli. 1024 doğal boyut.",
    ),
    "openai-3-large-1024": Candidate(
        key="openai-3-large-1024",
        provider="openai",
        model="text-embedding-3-large",
        dim=1024,
        usd_per_million_tokens=0.13,
        notes="3072 doğal boyut; `dimensions=1024` ile kısaltılır.",
    ),
    "e5-large": Candidate(
        key="e5-large",
        provider="local",
        model="intfloat/multilingual-e5-large",
        dim=1024,
        usd_per_million_tokens=0.0,
        self_hosted=True,
        notes="Self-host. Maliyet = VPS/GPU amortismanı; API ücreti yok. "
              "Model kartı 'query: ' öneki zorunlu kılar.",
        text_prefix="query: ",
    ),
    "bge-m3": Candidate(
        key="bge-m3",
        provider="local",
        model="BAAI/bge-m3",
        dim=1024,
        usd_per_million_tokens=0.0,
        self_hosted=True,
        notes="Self-host, çok dilli, 1024 boyut.",
    ),
}


# ------------------------------------------------------------------ sağlayıcı
class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def build_embedder(c: Candidate) -> Embedder:
    """Aday için embedder üretir. Anahtar/paket eksikse anlaşılır hata verir."""
    if c.provider == "voyage":
        return _VoyageEmbedder(c)
    if c.provider == "cohere":
        return _CohereEmbedder(c)
    if c.provider == "openai":
        return _OpenAIEmbedder(c)
    if c.provider == "local":
        return _LocalEmbedder(c)
    raise ValueError(f"Bilinmeyen sağlayıcı: {c.provider}")


class _VoyageEmbedder:
    def __init__(self, c: Candidate) -> None:
        import voyageai  # type: ignore[import-not-found]

        _require_env("VOYAGE_API_KEY")
        self.client = voyageai.Client()
        self.model = c.model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.client.embed(texts, model=self.model, input_type="document").embeddings


class _CohereEmbedder:
    def __init__(self, c: Candidate) -> None:
        import cohere  # type: ignore[import-not-found]

        _require_env("COHERE_API_KEY")
        self.client = cohere.ClientV2()
        self.model = c.model

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self.client.embed(
            texts=texts,
            model=self.model,
            input_type="search_document",
            embedding_types=["float"],
        )
        return resp.embeddings.float_


class _OpenAIEmbedder:
    def __init__(self, c: Candidate) -> None:
        from openai import OpenAI  # type: ignore[import-not-found]

        _require_env("OPENAI_API_KEY")
        self.client = OpenAI()
        self.model = c.model
        self.dim = c.dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self.client.embeddings.create(
            input=texts, model=self.model, dimensions=self.dim
        )
        return [d.embedding for d in resp.data]


class _LocalEmbedder:
    def __init__(self, c: Candidate) -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

        self.model = SentenceTransformer(c.model)
        self.prefix = c.text_prefix

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.prefix:
            texts = [self.prefix + t for t in texts]
        return [v.tolist() for v in self.model.encode(texts, normalize_embeddings=False)]


def _require_env(name: str) -> None:
    if not os.environ.get(name):
        raise RuntimeError(f"{name} ortam değişkeni ayarlı değil.")


# ---------------------------------------------------------------- metrikler
def cosine(u: list[float], v: list[float]) -> float:
    dot = sum(x * y for x, y in zip(u, v, strict=True))
    nu = math.sqrt(sum(x * x for x in u))
    nv = math.sqrt(sum(y * y for y in v))
    if nu == 0 or nv == 0:
        return 0.0
    return dot / (nu * nv)


def roc_auc(scores: list[float], labels: list[bool]) -> float:
    """Mann-Whitney U üzerinden ROC-AUC (bağlar için ortalama sıra)."""
    positives = [s for s, y in zip(scores, labels, strict=True) if y]
    negatives = [s for s, y in zip(scores, labels, strict=True) if not y]
    if not positives or not negatives:
        raise ValueError("Hem aynı-olay hem farklı-olay çifti gerekli.")

    ordered = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and scores[ordered[j + 1]] == scores[ordered[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[ordered[k]] = avg_rank
        i = j + 1

    rank_sum_pos = sum(r for r, y in zip(ranks, labels, strict=True) if y)
    n_pos, n_neg = len(positives), len(negatives)
    u = rank_sum_pos - n_pos * (n_pos + 1) / 2
    return u / (n_pos * n_neg)


@dataclass(frozen=True)
class ThresholdPoint:
    threshold: float
    precision: float
    recall: float
    f1: float


def threshold_sweep(scores: list[float], labels: list[bool]) -> list[ThresholdPoint]:
    points: list[ThresholdPoint] = []
    for t in sorted({round(s, 4) for s in scores}):
        tp = sum(1 for s, y in zip(scores, labels, strict=True) if s >= t and y)
        fp = sum(1 for s, y in zip(scores, labels, strict=True) if s >= t and not y)
        fn = sum(1 for s, y in zip(scores, labels, strict=True) if s < t and y)
        precision = tp / (tp + fp) if tp + fp else 1.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        points.append(ThresholdPoint(t, precision, recall, f1))
    return points


def recommend_thresholds(points: list[ThresholdPoint]) -> tuple[float, float]:
    """(T_HIGH, T_LOW) önerir.

    Spec §11.4: precision, recall'a TERCİH EDİLİR — yanlış birleştirme,
    ayrı kalmaktan daha zararlıdır.
      T_HIGH: precision >= 0.98 sağlayan en düşük eşik (otomatik atama)
      T_LOW : recall >= 0.95 sağlayan en yüksek eşik (denetim kuyruğu alt sınırı)
    """
    high_candidates = [p for p in points if p.precision >= 0.98]
    t_high = min((p.threshold for p in high_candidates), default=max(
        p.threshold for p in points))

    low_candidates = [p for p in points if p.recall >= 0.95]
    t_low = max((p.threshold for p in low_candidates), default=min(
        p.threshold for p in points))

    if t_low >= t_high:
        t_low = round(t_high - 0.08, 4)
    return t_high, t_low


# ------------------------------------------------------------------ koşucu
def load_pairs(path: Path) -> list[Pair]:
    pairs: list[Pair] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{lineno}: geçersiz JSON — {exc}") from exc
        pairs.append(
            Pair(
                id=raw["id"],
                a=raw["a"],
                b=raw["b"],
                same_event=bool(raw["same_event"]),
                difficulty=raw.get("difficulty", "easy"),
                note=raw.get("note", ""),
            )
        )
    return pairs


def validate_pairs(pairs: list[Pair]) -> list[str]:
    """F0-13 DoD'un veri koşullarını denetler."""
    problems: list[str] = []
    same = sum(1 for p in pairs if p.same_event)
    diff = len(pairs) - same

    if len(pairs) < 60:
        problems.append(f"En az 60 çift gerekli, {len(pairs)} var.")
    if same < 30:
        problems.append(f"En az 30 'aynı olay' çifti gerekli, {same} var.")
    if diff < 30:
        problems.append(f"En az 30 'farklı olay' çifti gerekli, {diff} var.")
    if sum(1 for p in pairs if p.difficulty == "hard") < 10:
        problems.append("En az 10 'hard' (yakın ama farklı olay) çifti önerilir.")

    ids = [p.id for p in pairs]
    if len(set(ids)) != len(ids):
        problems.append("Yinelenen çift id'leri var.")
    return problems


@dataclass
class Result:
    candidate: Candidate
    auc: float
    t_high: float
    t_low: float
    precision_at_high: float
    recall_at_low: float
    mean_same: float
    mean_diff: float
    hard_auc: float | None


def embed_in_batches(
    embedder: Embedder,
    texts: list[str],
    *,
    batch_size: int = 0,
    pause_seconds: float = 0.0,
) -> list[list[float]]:
    """Metinleri parça parça embed eder — sağlayıcı oran sınırları için.

    Barındırılan sağlayıcıların ücretsiz katmanları dakika başına hem
    istek hem token sınırı koyar (ör. Voyage: 3 RPM / 10K TPM). 120 kısa
    metni tek çağrıda göndermek bu sınırı aşar ve aday **kalitesizliğinden
    değil, faturalandırmasından** elenir — ölçümün geçersiz olmasıdır.

    `batch_size=0` bölme yapmaz (self-host adayları için varsayılan).
    """
    if batch_size <= 0 or len(texts) <= batch_size:
        return embedder.embed(texts)

    out: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        chunk = texts[start:start + batch_size]
        out.extend(embedder.embed(chunk))
        if pause_seconds and start + batch_size < len(texts):
            print(f"   ... oran siniri icin {pause_seconds:g} sn bekleniyor", flush=True)
            time.sleep(pause_seconds)
    return out


def run_candidate(
    c: Candidate,
    pairs: list[Pair],
    *,
    batch_size: int = 0,
    pause_seconds: float = 0.0,
) -> Result:
    embedder = build_embedder(c)

    texts = [p.a for p in pairs] + [p.b for p in pairs]
    if c.self_hosted:
        batch_size, pause_seconds = 0, 0.0  # yerel modelde oran sınırı yok
    vectors = embed_in_batches(
        embedder, texts, batch_size=batch_size, pause_seconds=pause_seconds
    )

    dims = {len(v) for v in vectors}
    if dims != {REQUIRED_DIM}:
        raise SystemExit(
            f"{c.key}: boyut uyumsuz. Şema VECTOR({REQUIRED_DIM}) bekliyor, "
            f"model {sorted(dims)} üretti."
        )

    n = len(pairs)
    scores = [cosine(vectors[i], vectors[i + n]) for i in range(n)]
    labels = [p.same_event for p in pairs]

    points = threshold_sweep(scores, labels)
    t_high, t_low = recommend_thresholds(points)

    at_high = next((p for p in points if p.threshold == t_high), None)
    at_low = next((p for p in points if p.threshold == t_low), None)

    hard_idx = [i for i, p in enumerate(pairs) if p.difficulty == "hard"]
    hard_auc = None
    if len({labels[i] for i in hard_idx}) == 2:
        hard_auc = roc_auc([scores[i] for i in hard_idx], [labels[i] for i in hard_idx])

    same_scores = [s for s, y in zip(scores, labels, strict=True) if y]
    diff_scores = [s for s, y in zip(scores, labels, strict=True) if not y]

    return Result(
        candidate=c,
        auc=roc_auc(scores, labels),
        t_high=t_high,
        t_low=t_low,
        precision_at_high=at_high.precision if at_high else float("nan"),
        recall_at_low=at_low.recall if at_low else float("nan"),
        mean_same=sum(same_scores) / len(same_scores),
        mean_diff=sum(diff_scores) / len(diff_scores),
        hard_auc=hard_auc,
    )


def render_report(results: list[Result], n_pairs: int) -> str:
    lines = [
        "# Embedding Benchmark Sonuclari (F0-13 / D16)",
        "",
        f"Cift sayisi: {n_pairs}",
        "",
        "| Aday | ROC-AUC | Zor AUC | T_HIGH | prec@HIGH | T_LOW | rec@LOW | "
        "ort.ayni | ort.farkli | $/M tok |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(results, key=lambda x: x.auc, reverse=True):
        hard = f"{r.hard_auc:.3f}" if r.hard_auc is not None else "-"
        price = (
            "self-host"
            if r.candidate.self_hosted
            else f"{r.candidate.usd_per_million_tokens:.3f}"
        )
        lines.append(
            f"| {r.candidate.key} | {r.auc:.4f} | {hard} | {r.t_high:.3f} | "
            f"{r.precision_at_high:.3f} | {r.t_low:.3f} | {r.recall_at_low:.3f} | "
            f"{r.mean_same:.3f} | {r.mean_diff:.3f} | {price} |"
        )
    lines += [
        "",
        "**Okuma notu:** Spec §11.4 precision'i recall'a tercih eder. T_HIGH",
        "otomatik atama esigidir (precision >= 0.98 hedefi); T_LOW insan denetim",
        "kuyrugunun alt siniridir (recall >= 0.95 hedefi). Nihai kalibrasyon",
        "Faz 2'de Golden Set uzerinde yapilir (F2-14).",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Embedding benchmark (F0-13)")
    parser.add_argument("--pairs", type=Path, default=REPO_ROOT / "eval" / "pairs_tr.jsonl")
    parser.add_argument(
        "--candidates",
        default="voyage-3,cohere-multilingual-3,e5-large",
        help="Virgülle ayrılmış aday anahtarları",
    )
    parser.add_argument("--out", type=Path, help="Rapor markdown çıktısı")
    parser.add_argument("--list-candidates", action="store_true")
    parser.add_argument(
        "--validate-only", action="store_true", help="Yalnızca çift setini denetle"
    )
    parser.add_argument(
        "--batch-size", type=int, default=0,
        help="Barındırılan sağlayıcıya kaç metin birden gönderilsin "
             "(0 = hepsi). Ücretsiz katman oran sınırları için kullanılır.",
    )
    parser.add_argument(
        "--pause-seconds", type=float, default=0.0,
        help="Partiler arası bekleme (oran sınırı için)",
    )
    args = parser.parse_args()

    if args.list_candidates:
        for c in CANDIDATES.values():
            host = "self-host" if c.self_hosted else f"{c.usd_per_million_tokens:.3f} $/M"
            print(f"{c.key:<24} {c.provider:<8} dim={c.dim} {host:<14} {c.notes}")
        return 0

    if not args.pairs.exists():
        print(
            f"Cift dosyasi yok: {args.pairs}\n"
            "eval/pairs_tr.README.md dosyasindaki bicimi kullanarak olusturun.",
            file=sys.stderr,
        )
        return 2

    pairs = load_pairs(args.pairs)
    problems = validate_pairs(pairs)
    if problems:
        print("Cift seti DoD kosullarini karsilamiyor:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        if args.validate_only:
            return 1
        print("  (yine de kosuluyor; rapora bu uyari yazilmali)", file=sys.stderr)
    elif args.validate_only:
        print(f"[OK] Cift seti gecerli: {len(pairs)} cift.")
        return 0

    keys = [k.strip() for k in args.candidates.split(",") if k.strip()]
    unknown = [k for k in keys if k not in CANDIDATES]
    if unknown:
        print(f"Bilinmeyen aday(lar): {unknown}", file=sys.stderr)
        return 2
    if len(keys) < 3:
        print("UYARI: F0-13 DoD en az 3 aday istiyor.", file=sys.stderr)

    results: list[Result] = []
    for key in keys:
        print(f"-> kosuluyor: {key}")
        try:
            results.append(run_candidate(
                CANDIDATES[key], pairs,
                batch_size=args.batch_size, pause_seconds=args.pause_seconds,
            ))
        except Exception as exc:  # noqa: BLE001
            print(f"   ATLANDI ({type(exc).__name__}): {exc}", file=sys.stderr)

    if not results:
        print("Hicbir aday kosturulamadi.", file=sys.stderr)
        return 1

    report = render_report(results, len(pairs))
    print("\n" + report)
    if args.out:
        args.out.write_text(report + "\n", encoding="utf-8")
        print(f"\nRapor yazildi: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
