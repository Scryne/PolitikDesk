"""LLM katmanı hata tipleri."""

from __future__ import annotations


class LLMError(Exception):
    """LLM katmanındaki tüm hataların ortak atası."""


class BudgetExceeded(LLMError):
    """Günlük veya aylık maliyet tavanı aşıldı (Spec §11.5, F4-07).

    Bu hata alındığında ÜRETİM durur, INGESTION devam eder — kanıt zinciri
    birikmeye devam etsin, yalnızca LLM harcaması dursun.
    """

    def __init__(self, period: str, spent_usd: float, cap_usd: float) -> None:
        self.period = period
        self.spent_usd = spent_usd
        self.cap_usd = cap_usd
        super().__init__(
            f"{period} LLM bütçesi aşıldı: {spent_usd:.4f} $ / tavan {cap_usd:.2f} $"
        )


class LLMRefusal(LLMError):
    """Model güvenlik sınıflandırıcısı isteği reddetti (stop_reason='refusal').

    HTTP hatası değildir; 200 döner ve içerik boş/kısmi olur. Çağıran taraf
    bunu içerik sonucu olarak ele almalıdır.
    """

    def __init__(self, category: str | None, explanation: str | None = None) -> None:
        self.category = category
        self.explanation = explanation
        super().__init__(f"Model isteği reddetti (kategori={category}): {explanation}")


class SchemaValidationError(LLMError):
    """Model çıktısı beklenen JSON şemasına uymadı."""
