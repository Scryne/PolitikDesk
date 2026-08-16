"""LLM katmanı hata tipleri."""

from __future__ import annotations


class LLMError(Exception):
    """LLM katmanındaki tüm hataların ortak atası."""


class LLMNotConfigured(LLMError):
    """API anahtarı tanımlı değil — çağrı hiç denenmedi.

    Bu hata olay başına yakalanmaz, tur başında yükselir: anahtar yokken
    50 olayın 50'sinde ayrı ayrı çuvallamak, tek bir yapılandırma
    eksikliğini 50 satır anlamsız hata gibi gösteriyordu.
    """

    def __init__(self, variable: str = "ANTHROPIC_API_KEY") -> None:
        self.variable = variable
        super().__init__(
            f"{variable} tanımlı değil. `.env` dosyasına ekleyin "
            f"(bkz. .env.example) veya ortam değişkeni olarak verin. "
            f"Not: `.env` yalnızca CLI girişleri `config.load_env_file()` "
            f"çağırdığında sürecin ortamına yüklenir."
        )


class LLMHTTPError(LLMError):
    """Sağlayıcı HTTP hata döndürdü (OpenAI uyumlu arka uç).

    Gövdeyi kısaltarak taşır: 400'lerin sebebi neredeyse her zaman gövdede
    yazar ("response_format not supported" gibi) ve o metin olmadan hata
    ayıklamak imkânsızdır.
    """

    def __init__(self, status_code: int, body: str, url: str = "") -> None:
        self.status_code = status_code
        self.body = body
        self.url = url
        super().__init__(f"LLM sağlayıcısı HTTP {status_code} döndürdü: {body[:400]}")


class BudgetExceeded(LLMError):
    """Günlük veya aylık maliyet tavanı aşıldı (Spec §11.5, F4-07).

    Bu hata alındığında ÜRETİM durur, INGESTION devam eder — kanıt zinciri
    birikmeye devam etsin, yalnızca LLM harcaması dursun.
    """

    def __init__(self, period: str, spent_usd: float, cap_usd: float) -> None:
        self.period = period
        self.spent_usd = spent_usd
        self.cap_usd = cap_usd
        super().__init__(f"{period} LLM bütçesi aşıldı: {spent_usd:.4f} $ / tavan {cap_usd:.2f} $")


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
