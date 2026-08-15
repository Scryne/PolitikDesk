"""LLM model kıyaslaması — iddia çıkarımı görevinde (D17, B-67).

Model seçimi tahminle değil ölçümle yapılır. D16'da embedding kararı
`eval/embedding_benchmark.py` ile verilmişti; bu, aynı yaklaşımın LLM
tarafıdır.

**Neden yer gerçeği (ground truth) olmadan da ölçülebilir:** iddia
çıkarımının DoD'si zaten programatik olarak denetlenebilir dört şey
istiyor ve bunların hiçbiri "doğru iddia hangisiydi" bilgisine ihtiyaç
duymaz:

  F2-06  Çıktı şemaya uyuyor mu           -> JSON + şema geçerliliği
  F2-07  claim_type doğru mu              -> enum + tip/alan tutarlılığı
  F2-08  Sayısal normalizasyon doğru mu   -> metric/value/unit/period
  F2-10  Alıntı metinde BİREBİR geçiyor mu -> verify_quote()

Bunlardan en ayırt edicisi **alıntı sadakati**: uydurulmuş alıntı nesnel
olarak yanlıştır ve yer gerçeği olmadan yakalanır. Zayıf model burada
dökülür.

Girdi olarak Golden Set'in gerçek Türkçe makaleleri kullanılır
(`eval/golden_set_v1.jsonl`) — sentetik metin değil.

Kullanım:
    python -m scripts.llm_benchmark --articles 8
    python -m scripts.llm_benchmark --models meta/llama-3.3-70b-instruct
    python -m scripts.llm_benchmark --provider anthropic --models claude-sonnet-5
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from politikdesk.config import Settings, load_env_file
from politikdesk.llm.budget import BudgetGuard, InMemoryLedger
from politikdesk.llm.client import LLMClient, build_backend
from politikdesk.nlp.claims import extract_claims

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_ARTICLES = REPO_ROOT / "eval" / "golden_set_v1.jsonl"

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Aday havuzu: anahtara açık, metin üreten, yeterince büyük modeller.
# Gömme (embedding), güvenlik sınıflandırıcısı, görüntü ve kod modelleri
# bu görevle ilgisiz olduğu için havuzda yok.
DEFAULT_CANDIDATES: tuple[str, ...] = (
    "moonshotai/kimi-k2.6",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3-super-120b-a12b",
    "deepseek-ai/deepseek-v4-flash-0731",
    "z-ai/glm-5.2",
    "minimaxai/minimax-m3",
    "openai/gpt-oss-120b",
    "meta/llama-3.3-70b-instruct",
)


@dataclass
class ModelScore:
    """Bir modelin tek turluk karnesi."""

    model: str
    articles: int = 0
    call_errors: int = 0
    error_types: dict[str, int] = field(default_factory=dict)
    raw_claims: int = 0
    accepted: int = 0
    rejected: int = 0
    quote_failures: int = 0
    type_failures: int = 0
    value_failures: int = 0
    forbidden_fields: int = 0
    latency_ms_total: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    json_mode: str = ""

    # -- türetilmiş ölçütler ------------------------------------------------
    @property
    def ok_calls(self) -> int:
        return self.articles - self.call_errors

    @property
    def acceptance_rate(self) -> float:
        """Çıkarılan iddiaların kaçı doğrulamadan geçti."""
        return self.accepted / self.raw_claims if self.raw_claims else 0.0

    @property
    def quote_fidelity(self) -> float:
        """Alıntısı kaynak metinde birebir geçen iddia oranı (F2-10)."""
        if not self.raw_claims:
            return 0.0
        return 1 - (self.quote_failures / self.raw_claims)

    @property
    def yield_per_article(self) -> float:
        return self.accepted / self.ok_calls if self.ok_calls else 0.0

    @property
    def avg_latency_ms(self) -> int:
        return self.latency_ms_total // self.ok_calls if self.ok_calls else 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "ok_calls": self.ok_calls,
            "call_errors": self.call_errors,
            "error_types": self.error_types,
            "raw_claims": self.raw_claims,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "acceptance_rate": round(self.acceptance_rate, 3),
            "quote_fidelity": round(self.quote_fidelity, 3),
            "quote_failures": self.quote_failures,
            "type_failures": self.type_failures,
            "value_failures": self.value_failures,
            "forbidden_fields": self.forbidden_fields,
            "yield_per_article": round(self.yield_per_article, 2),
            "avg_latency_ms": self.avg_latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "json_mode": self.json_mode,
        }


def load_articles(path: Path, limit: int) -> list[dict[str, Any]]:
    """Golden Set'ten örnek seçer — deterministik ve zorluk dengeli.

    Rastgele örnek, koşumlar arası karşılaştırmayı imkânsız kılardı.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    usable = sorted(
        (r for r in rows if len(r.get("excerpt") or "") >= 80),
        key=lambda r: str(r["article_id"]),
    )
    by_difficulty: dict[str, list[dict[str, Any]]] = {}
    for row in usable:
        by_difficulty.setdefault(str(row.get("difficulty", "?")), []).append(row)

    picked: list[dict[str, Any]] = []
    while len(picked) < limit and any(by_difficulty.values()):
        for bucket in sorted(by_difficulty):
            if by_difficulty[bucket] and len(picked) < limit:
                picked.append(by_difficulty[bucket].pop(0))
    return picked


def _settings_for(provider: str, model: str, timeout: float = 180.0, retries: int = 4) -> Settings:
    if provider == "anthropic":
        return Settings(
            env="test",
            llm_provider="anthropic",
            llm_model_extraction=model,
            llm_model_generation=model,
        )
    return Settings(
        env="test",
        llm_provider="openai_compat",
        llm_base_url=NVIDIA_BASE_URL,
        llm_api_key_env="NVIDIA_API_KEY",
        llm_model_extraction=model,
        llm_model_generation=model,
        llm_timeout_seconds=timeout,
        llm_max_retries=retries,
    )


def score_model(
    provider: str,
    model: str,
    articles: list[dict[str, Any]],
    verbose: bool = False,
    timeout: float = 180.0,
    retries: int = 4,
) -> ModelScore:
    """Bir modeli örnek makaleler üzerinde koşar ve karnesini çıkarır."""
    score = ModelScore(model=model)
    settings = _settings_for(provider, model, timeout=timeout, retries=retries)
    backend = build_backend(settings)
    # Defter bellekte: kıyas koşumu `llm_calls` muhasebesini kirletmemeli.
    client = LLMClient(
        backend=backend,
        guard=BudgetGuard(ledger=InMemoryLedger(), settings=settings),
        settings=settings,
    )

    for article in articles:
        score.articles += 1
        started = time.perf_counter()
        try:
            result = extract_claims(
                title=article["title"],
                excerpt=article["excerpt"],
                source_name=str(article.get("source", "bilinmiyor")),
                tier=2,
                published_at=str(article.get("published_at", "")),
                client=client,
            )
        except Exception as exc:  # noqa: BLE001 — kıyasta her hata veridir
            score.call_errors += 1
            name = type(exc).__name__
            score.error_types[name] = score.error_types.get(name, 0) + 1
            if verbose:
                print(f"    ! {name}: {str(exc)[:160]}")
            continue

        score.latency_ms_total += int((time.perf_counter() - started) * 1000)
        score.accepted += len(result.claims)
        score.rejected += len(result.rejected)
        score.raw_claims += len(result.claims) + len(result.rejected)

        for claim in result.rejected:
            for problem in claim.problems:
                if "uydurulmus alinti" in problem or "bulunamadi" in problem:
                    score.quote_failures += 1
                elif "claim_type" in problem:
                    score.type_failures += 1
                elif "normalized_value" in problem or "metric" in problem or "period" in problem:
                    score.value_failures += 1
                elif "yasak alan" in problem:
                    score.forbidden_fields += 1

        if verbose and result.claims:
            for claim in result.claims[:2]:
                print(f"    + [{claim.claim_type}] {claim.claim_text[:88]}")

    ledger = client.guard.ledger
    if isinstance(ledger, InMemoryLedger):
        score.input_tokens = sum(c.input_tokens for c in ledger.calls)
        score.output_tokens = sum(c.output_tokens for c in ledger.calls)
    score.json_mode = getattr(backend, "_mode", "-")
    return score


def render_table(scores: list[ModelScore]) -> str:
    """Karar tablosu — alıntı sadakatine göre sıralı."""
    header = (
        "| Model | Çağrı | Ham | Kabul | Kabul or. | Alıntı sadakati | "
        "Uydurma | Tip h. | Değer h. | Makale başına | Gecikme | Mod |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|\n"
    )
    rows = []
    for s in sorted(scores, key=lambda x: (-x.quote_fidelity, -x.acceptance_rate)):
        rows.append(
            f"| `{s.model}` | {s.ok_calls}/{s.articles} | {s.raw_claims} | {s.accepted} | "
            f"{s.acceptance_rate:.0%} | **{s.quote_fidelity:.0%}** | {s.quote_failures} | "
            f"{s.type_failures} | {s.value_failures} | {s.yield_per_article:.1f} | "
            f"{s.avg_latency_ms} ms | {s.json_mode} |"
        )
    return header + "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    load_env_file()

    parser = argparse.ArgumentParser(description="LLM model kıyaslaması (iddia çıkarımı)")
    parser.add_argument(
        "--provider", choices=["openai_compat", "anthropic"], default="openai_compat"
    )
    parser.add_argument("--models", help="Virgülle ayrık model listesi")
    parser.add_argument("--articles", type=int, default=8)
    parser.add_argument("--golden", type=Path, default=GOLDEN_ARTICLES)
    parser.add_argument("--out", type=Path, help="Sonucu JSON olarak kaydet")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    models = (
        [m.strip() for m in args.models.split(",") if m.strip()]
        if args.models
        else list(DEFAULT_CANDIDATES)
    )
    articles = load_articles(args.golden, args.articles)
    print(f"{len(articles)} makale x {len(models)} model = {len(articles) * len(models)} çağrı\n")

    scores: list[ModelScore] = []
    for model in models:
        print(f"-> {model}")
        score = score_model(
            args.provider,
            model,
            articles,
            verbose=args.verbose,
            timeout=args.timeout,
            retries=args.retries,
        )
        scores.append(score)
        print(
            f"   kabul {score.accepted}/{score.raw_claims} "
            f"| alıntı sadakati {score.quote_fidelity:.0%} "
            f"| hata {score.call_errors} | {score.avg_latency_ms} ms | mod={score.json_mode}\n"
        )

    print(render_table(scores))

    if args.out:
        args.out.write_text(
            json.dumps([s.as_dict() for s in scores], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nJSON: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
