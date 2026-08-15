"""Üretim modeli kıyaslaması — taslak yazımı görevinde (B-71, B-67).

D17 (`docs/llm-model-benchmark.md`) **yalnızca çıkarım** görevini ölçtü ve
kapsam sınırını açıkça yazdı: "`PD_LLM_MODEL_GENERATION` şimdilik aynı
modele ayarlandı ama bu bir karar değil, yer tutucudur." Bu betik o
kararı verir.

**Neden yer gerçeği olmadan da ölçülebilir — ve neden bu ölçüt daha
sert:** taslak üretiminin kapısı (G3 koşul 2) zaten nesnel ve ikili bir
şey istiyor: *"taslakta kanıtta olmayan sayı/tarih = %0"*. Bunu ölçmek
için "iyi taslak hangisiydi" bilgisine ihtiyaç yoktur; kanıt seti
bilinir, üretilen metin bilinir, `grounding_check` ikisini karşılaştırır.

Ölçülen dört şey:

  1. **Grounding oranı**   Kanıt dışı sayı/tarih/alıntı üretmeyen taslak
                           oranı. Kapı bu; ayırt edici ölçüt bu. (F3-12)
  2. **Sözleşme uyumu**    Uydurulmuş `cited_claim_ids`, yasak alan,
                           boş gövde. (F3-10)
  3. **Güvenilirlik**      Çağrının dönüp dönmediği. D17'de ayırt edici
                           olan buydu; ücretsiz katmanda hâlâ geçerli.
  4. **Maliyet/gecikme**   Üretim modeli çıkarımdan pahalıdır; birim
                           ekonomi hedefi ≤ 8 $/ay (Spec §13.3).

Girdi: `eval/golden_claims_v1.jsonl` — gerçek Türkçe makro-ekonomi
iddiaları ve kanıt bağları, elle etiketlenmiş `evidence_status` ile.

Kullanım:
    python -m scripts.generation_benchmark --events 4
    python -m scripts.generation_benchmark --provider anthropic --models claude-opus-5
    python -m scripts.generation_benchmark --angles inform,critique --out sonuc.json
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from politikdesk.config import Settings, load_env_file
from politikdesk.editorial.generator import ANGLES, generate_draft
from politikdesk.editorial.guards import ClaimForGeneration, GenerationBlocked
from politikdesk.llm.budget import BudgetGuard, InMemoryLedger
from politikdesk.llm.client import LLMClient, build_backend

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_CLAIMS = REPO_ROOT / "eval" / "golden_claims_v1.jsonl"

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Aday havuzu. D17'nin hayatta kalanları + Claude (B-67 karşılaştırması).
# Üretim görevi çıkarımdan farklıdır (uzun metin, üslup, tutarlılık), o
# yüzden D17'nin sıralaması buraya devredilmez.
DEFAULT_CANDIDATES: tuple[str, ...] = (
    "nvidia/nemotron-3-super-120b-a12b",
    "deepseek-ai/deepseek-v4-flash-0731",
    "openai/gpt-oss-120b",
    "z-ai/glm-5.2",
)


@dataclass
class GenerationScore:
    """Bir modelin taslak üretimi karnesi."""

    model: str
    attempts: int = 0
    call_errors: int = 0
    error_types: dict[str, int] = field(default_factory=dict)
    drafts: int = 0
    grounded: int = 0
    grounding_issues: int = 0
    issue_kinds: dict[str, int] = field(default_factory=dict)
    contract_problems: int = 0
    empty_citations: int = 0
    marked_commentary: int = 0
    body_chars_total: int = 0
    latency_ms_total: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    samples: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok_calls(self) -> int:
        return self.attempts - self.call_errors

    @property
    def grounding_rate(self) -> float:
        """Kapı G3 #2'nin vekil ölçütü: kanıt dışı öğe İÇERMEYEN taslak oranı."""
        return self.grounded / self.drafts if self.drafts else 0.0

    @property
    def contract_rate(self) -> float:
        return 1 - (self.contract_problems / self.drafts) if self.drafts else 0.0

    @property
    def completion_rate(self) -> float:
        return self.ok_calls / self.attempts if self.attempts else 0.0

    @property
    def avg_latency_ms(self) -> int:
        return self.latency_ms_total // self.ok_calls if self.ok_calls else 0

    @property
    def avg_chars(self) -> int:
        return self.body_chars_total // self.drafts if self.drafts else 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "attempts": self.attempts,
            "ok_calls": self.ok_calls,
            "call_errors": self.call_errors,
            "error_types": self.error_types,
            "drafts": self.drafts,
            "grounded": self.grounded,
            "grounding_rate": round(self.grounding_rate, 3),
            "grounding_issues": self.grounding_issues,
            "issue_kinds": self.issue_kinds,
            "contract_problems": self.contract_problems,
            "contract_rate": round(self.contract_rate, 3),
            "empty_citations": self.empty_citations,
            "marked_commentary": self.marked_commentary,
            "avg_chars": self.avg_chars,
            "avg_latency_ms": self.avg_latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
        }


def load_events(path: Path, limit: int) -> list[tuple[str, list[ClaimForGeneration]]]:
    """Golden Set iddialarını olaya göre gruplar.

    Seçim deterministiktir (olay kimliğine göre sıralı, iddia sayısı
    fazla olanlar önce): rastgele örnek, koşumlar arası karşılaştırmayı
    imkânsız kılardı — D17'nin aynı gerekçesi.
    """
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]

    by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_event[str(row["event_id"])].append(row)

    events: list[tuple[str, list[ClaimForGeneration]]] = []
    for event_id in sorted(by_event, key=lambda e: (-len(by_event[e]), e)):
        claims = [
            ClaimForGeneration(
                # Golden Set kimlikleri metin ("gc-001"); üretim şeması
                # tamsayı ister. Sıra numarası kullanılır.
                claim_id=index + 1,
                claim_text=row["claim_text"],
                claim_type=row["claim_type"],
                evidence_status=row["expected_status"],
                status_rule=row.get("expected_rule", ""),
                normalized_value=row.get("normalized_value"),
                evidence=tuple(
                    {
                        "stance": ev.get("stance", "supports"),
                        "quote_span": ev.get("text", ""),
                        "source_name": ev.get("source_slug", "kaynak"),
                        "source_slug": ev.get("source_slug", ""),
                        "tier": ev.get("tier", 3),
                    }
                    for ev in row.get("evidence", [])
                ),
            )
            for index, row in enumerate(by_event[event_id])
        ]
        if len(claims) >= 2:
            events.append((event_id, claims))
        if len(events) >= limit:
            break
    return events


def _settings_for(provider: str, model: str, timeout: float, retries: int) -> Settings:
    if provider == "anthropic":
        return Settings(
            env="test",
            llm_provider="anthropic",
            llm_model_extraction=model,
            llm_model_generation=model,
            llm_timeout_seconds=timeout,
            llm_max_retries=retries,
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
    events: list[tuple[str, list[ClaimForGeneration]]],
    angles: list[str],
    *,
    verbose: bool = False,
    timeout: float = 240.0,
    retries: int = 3,
) -> GenerationScore:
    """Bir modeli olay × açı ızgarasında koşar ve karnesini çıkarır."""
    score = GenerationScore(model=model)
    settings = _settings_for(provider, model, timeout, retries)
    backend = build_backend(settings)
    # Defter bellekte: kıyas koşumu `llm_calls` muhasebesini kirletmemeli.
    client = LLMClient(
        backend=backend,
        guard=BudgetGuard(ledger=InMemoryLedger(), settings=settings),
        settings=settings,
    )

    for event_id, claims in events:
        for angle in angles:
            score.attempts += 1
            started = time.perf_counter()
            try:
                draft = generate_draft(angle=angle, claims=claims, client=client)
            except GenerationBlocked as blocked:
                # Kapı devrede: model hatası değil, ürün sözleşmesi.
                score.attempts -= 1
                if verbose:
                    print(f"    · {event_id}/{angle}: kapı — {blocked.reason}")
                continue
            except Exception as exc:  # noqa: BLE001 — kıyasta her hata veridir
                score.call_errors += 1
                name = type(exc).__name__
                score.error_types[name] = score.error_types.get(name, 0) + 1
                if verbose:
                    print(f"    ! {event_id}/{angle} {name}: {str(exc)[:150]}")
                continue

            score.latency_ms_total += int((time.perf_counter() - started) * 1000)
            score.drafts += 1
            score.body_chars_total += len(draft.body)
            score.marked_commentary += len(draft.commentary_sentences)

            if draft.grounding.ok:
                score.grounded += 1
            for issue in draft.grounding.issues:
                score.grounding_issues += 1
                score.issue_kinds[issue.kind] = score.issue_kinds.get(issue.kind, 0) + 1

            if draft.problems:
                score.contract_problems += 1
            if not draft.cited_claim_ids:
                score.empty_citations += 1

            score.samples.append(
                {
                    "event": event_id,
                    "angle": angle,
                    "grounded": draft.grounding.ok,
                    "issues": [i.message for i in draft.grounding.issues],
                    "problems": list(draft.problems),
                    "body": draft.body,
                }
            )
            if verbose:
                mark = "OK " if draft.is_usable else "RED"
                print(f"    [{mark}] {event_id}/{angle}: {draft.body[:100]}")
                for issue in draft.grounding.issues:
                    print(f"           -> {issue.message}")

    ledger = client.guard.ledger
    if isinstance(ledger, InMemoryLedger):
        score.input_tokens = sum(c.input_tokens for c in ledger.calls)
        score.output_tokens = sum(c.output_tokens for c in ledger.calls)
        score.cost_usd = sum(c.cost_usd for c in ledger.calls)
    return score


def render_table(scores: list[GenerationScore]) -> str:
    """Karar tablosu — grounding oranına göre sıralı (kapı ölçütü)."""
    header = (
        "| Model | Çağrı | Taslak | **Grounding** | Kanıt dışı öğe | Sözleşme | "
        "Uydurma atıf | Ort. uzunluk | Gecikme | Maliyet |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    )
    rows = []
    for s in sorted(scores, key=lambda x: (-x.grounding_rate, -x.completion_rate)):
        kinds = ", ".join(f"{k}:{v}" for k, v in sorted(s.issue_kinds.items())) or "—"
        rows.append(
            f"| `{s.model}` | {s.ok_calls}/{s.attempts} | {s.drafts} | "
            f"**{s.grounding_rate:.0%}** | {s.grounding_issues} ({kinds}) | "
            f"{s.contract_rate:.0%} | {s.empty_citations} | {s.avg_chars} | "
            f"{s.avg_latency_ms} ms | ${s.cost_usd:.4f} |"
        )
    return header + "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    load_env_file()

    parser = argparse.ArgumentParser(description="Üretim modeli kıyaslaması (taslak yazımı, B-71)")
    parser.add_argument(
        "--provider", choices=["openai_compat", "anthropic"], default="openai_compat"
    )
    parser.add_argument("--models", help="Virgülle ayrık model listesi")
    parser.add_argument("--events", type=int, default=4)
    parser.add_argument(
        "--angles",
        default="inform,analyze,critique",
        help=f"Virgülle ayrık açı listesi. Seçenekler: {sorted(ANGLES)}",
    )
    parser.add_argument("--golden", type=Path, default=GOLDEN_CLAIMS)
    parser.add_argument("--out", type=Path, help="Sonucu JSON olarak kaydet")
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    models = (
        [m.strip() for m in args.models.split(",") if m.strip()]
        if args.models
        else list(DEFAULT_CANDIDATES)
    )
    angles = [a.strip() for a in args.angles.split(",") if a.strip()]
    unknown = [a for a in angles if a not in ANGLES]
    if unknown:
        parser.error(f"Bilinmeyen açı: {unknown}. Seçenekler: {sorted(ANGLES)}")

    events = load_events(args.golden, args.events)
    if not events:
        parser.error(f"{args.golden} içinde ≥2 iddialı olay bulunamadı.")

    total = len(events) * len(angles) * len(models)
    print(f"{len(events)} olay x {len(angles)} açı x {len(models)} model = {total} çağrı\n")

    scores: list[GenerationScore] = []
    for model in models:
        print(f"-> {model}")
        score = score_model(
            args.provider,
            model,
            events,
            angles,
            verbose=args.verbose,
            timeout=args.timeout,
            retries=args.retries,
        )
        scores.append(score)
        print(
            f"   grounding {score.grounded}/{score.drafts} "
            f"({score.grounding_rate:.0%}) | kanıt dışı öğe {score.grounding_issues} "
            f"| hata {score.call_errors} | {score.avg_latency_ms} ms "
            f"| ${score.cost_usd:.4f}\n"
        )

    print(render_table(scores))

    if args.out:
        args.out.write_text(
            json.dumps(
                [{**s.as_dict(), "samples": s.samples} for s in scores],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nJSON: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
