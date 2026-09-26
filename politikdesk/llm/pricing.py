"""Model fiyat tablosu ve maliyet hesabı (F0-17).

Fiyatlar 1 milyon token başına ABD doları cinsindendir.
Kaynak: Anthropic Claude API fiyatlandırması (Faz 0'da doğrulandı: 12 Ağu 2026).

Fiyat değiştiğinde YALNIZCA bu dosya güncellenir; maliyet modeli
(scripts/cost_model.py) ve bütçe sayacı aynı tabloyu okur.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final


@dataclass(frozen=True)
class ModelPrice:
    """1M token başına $ fiyat."""

    input_usd: float
    output_usd: float
    # Tanıtım fiyatı (varsa) ve son geçerlilik günü
    intro_input_usd: float | None = None
    intro_output_usd: float | None = None
    intro_until: date | None = None

    def rates(self, on: date) -> tuple[float, float]:
        if (
            self.intro_until is not None
            and self.intro_input_usd is not None
            and self.intro_output_usd is not None
            and on <= self.intro_until
        ):
            return self.intro_input_usd, self.intro_output_usd
        return self.input_usd, self.output_usd


# Ücretsiz katman: fiyat 0, ama model tabloda AÇIKÇA yer alır.
FREE_TIER: Final[ModelPrice] = ModelPrice(0.0, 0.0)

PRICES: Final[dict[str, ModelPrice]] = {
    "claude-fable-5": ModelPrice(10.00, 50.00),
    "claude-opus-5": ModelPrice(5.00, 25.00),
    "claude-opus-4-8": ModelPrice(5.00, 25.00),
    "claude-opus-4-7": ModelPrice(5.00, 25.00),
    "claude-sonnet-5": ModelPrice(
        3.00,
        15.00,
        intro_input_usd=2.00,
        intro_output_usd=10.00,
        intro_until=date(2026, 8, 31),
    ),
    "claude-sonnet-4-6": ModelPrice(3.00, 15.00),
    "claude-haiku-4-5": ModelPrice(1.00, 5.00),
    # --- OpenAI uyumlu ücretsiz katman (NVIDIA NIM · build.nvidia.com) ---
    # Buradaki 0, "bilinmiyor" değil "ücretsiz" demektir: model açıkça
    # tabloya yazılmıştır, dolayısıyla UnknownModelError invaryantı
    # (bilinmeyen model sessizce 0 maliyet üretmez) korunur. Token
    # muhasebesi yine tutulur — kota takibi ve sağlayıcı karşılaştırması
    # maliyetten bağımsız olarak token'a bakar.
    #
    # ⚠ Model kimliği build.nvidia.com'daki kartta yazan dizeyle BİREBİR
    #   aynı olmalıdır. Listede olmayan bir model seçilirse çağrı
    #   UnknownModelError ile durur ve bu dosyaya eklenmesi istenir.
    # Liste, anahtara açık modeller `/v1/models` ile doğrulanarak yazıldı
    # (13 Ağu 2026). Katalog kartında görünen her model her anahtara açık
    # değildir; tahmin yerine uç noktaya sorulmuştur.
    # 2026-09-26 yeniden doğrulama: aşağıdakiler /v1/models ile açık görüldü; emekliye
    # ayrılanlar (410 Gone) geçmiş kayıtların maliyet hesabı için listede tutuluyor.
    "deepseek-ai/deepseek-v4.1-flash": FREE_TIER,
    "z-ai/glm-5.3": FREE_TIER,
    "openai/gpt-oss-20b": FREE_TIER,
    "mistralai/mistral-nemotron": FREE_TIER,
    "moonshotai/kimi-k2.6": FREE_TIER,
    "nvidia/nemotron-3-ultra-550b-a55b": FREE_TIER,
    "nvidia/nemotron-3-super-120b-a12b": FREE_TIER,
    "nvidia/llama-3.3-nemotron-super-49b-v1.5": FREE_TIER,
    "deepseek-ai/deepseek-v4-flash-0731": FREE_TIER,
    "z-ai/glm-5.2": FREE_TIER,
    "minimaxai/minimax-m3": FREE_TIER,
    "openai/gpt-oss-120b": FREE_TIER,
    "meta/llama-3.3-70b-instruct": FREE_TIER,
    "meta/llama-3.1-70b-instruct": FREE_TIER,
    "meta/llama-3.1-8b-instruct": FREE_TIER,
    "qwen/qwen2.5-72b-instruct": FREE_TIER,
    "qwen/qwen2.5-coder-32b-instruct": FREE_TIER,
    "deepseek-ai/deepseek-r1": FREE_TIER,
    "deepseek-ai/deepseek-v3": FREE_TIER,
    "mistralai/mistral-large-2-instruct": FREE_TIER,
    "mistralai/mixtral-8x22b-instruct-v0.1": FREE_TIER,
    # --- Yerel / Self-Hosted Modeller (Ollama, LM Studio, vLLM · maliyetsiz) ---
    "local": FREE_TIER,
    "ollama": FREE_TIER,
    "llama3.3": FREE_TIER,
    "llama3.2": FREE_TIER,
    "llama3.1": FREE_TIER,
    "llama3": FREE_TIER,
    "qwen2.5": FREE_TIER,
    "qwen2.5:7b": FREE_TIER,
    "qwen2.5:7b-instruct": FREE_TIER,
    "qwen2.5:7b-instruct-q5_K_M": FREE_TIER,
    "qwen2.5:14b": FREE_TIER,
    "qwen2.5:14b-instruct": FREE_TIER,
    "qwen2.5:14b-instruct-q4_K_M": FREE_TIER,
    "qwen2.5-coder": FREE_TIER,
    "mistral": FREE_TIER,
    "gemma2": FREE_TIER,
    "phi4": FREE_TIER,
    "phi3": FREE_TIER,
    "deepseek-r1": FREE_TIER,
}

# Prompt cache çarpanları (girdi fiyatına göre)
CACHE_READ_MULTIPLIER: Final[float] = 0.10
CACHE_WRITE_5M_MULTIPLIER: Final[float] = 1.25
CACHE_WRITE_1H_MULTIPLIER: Final[float] = 2.00


class UnknownModelError(KeyError):
    """Fiyat tablosunda olmayan model — maliyet sessizce 0 sayılmaz."""


def estimate_cost_usd(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    on: date | None = None,
) -> float:
    """Bir çağrının maliyetini ABD doları olarak hesaplar.

    Bilinmeyen model sessizce 0 maliyet üretmez — bütçe tavanının
    farkında olmadan aşılmasını engellemek için hata fırlatır.
    Yerel ve self-hosted modeller (Ollama/vLLM) ise doğrudan FREE_TIER ($0.0) döner.
    """
    clean_model = model.strip()
    price = PRICES.get(clean_model)
    if price is None:
        # Yerel/self-hosted model tespiti (ollama/..., local/..., localhost/...)
        lower = clean_model.lower()
        local_keywords = (
            "llama",
            "qwen",
            "mistral",
            "gemma",
            "deepseek",
            "phi",
            "nemotron",
        )
        if (
            lower.startswith(("local", "ollama", "lmstudio", "vllm"))
            or ":latest" in lower
            or "-instruct" in lower
            or any(m in lower for m in local_keywords)
        ):
            price = FREE_TIER
        else:
            raise UnknownModelError(
                f"'{model}' fiyat tablosunda yok. politikdesk/llm/pricing.py güncellenmeli."
            )

    in_rate, out_rate = price.rates(on or date.today())
    per_token_in = in_rate / 1_000_000
    per_token_out = out_rate / 1_000_000

    return (
        input_tokens * per_token_in
        + output_tokens * per_token_out
        + cache_read_tokens * per_token_in * CACHE_READ_MULTIPLIER
        + cache_write_tokens * per_token_in * CACHE_WRITE_5M_MULTIPLIER
    )
