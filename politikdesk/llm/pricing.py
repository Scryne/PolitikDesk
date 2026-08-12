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
    """
    try:
        price = PRICES[model]
    except KeyError as exc:
        raise UnknownModelError(
            f"'{model}' fiyat tablosunda yok. politikdesk/llm/pricing.py güncellenmeli."
        ) from exc

    in_rate, out_rate = price.rates(on or date.today())
    per_token_in = in_rate / 1_000_000
    per_token_out = out_rate / 1_000_000

    return (
        input_tokens * per_token_in
        + output_tokens * per_token_out
        + cache_read_tokens * per_token_in * CACHE_READ_MULTIPLIER
        + cache_write_tokens * per_token_in * CACHE_WRITE_5M_MULTIPLIER
    )
