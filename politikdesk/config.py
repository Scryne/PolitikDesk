"""Uygulama ayarları — tek kaynak (F0-12).

Tüm ayarlar `PD_` önekli ortam değişkenlerinden okunur; API anahtarları
sağlayıcının kendi standart değişken adını kullanır (ANTHROPIC_API_KEY vb.).
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Final, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]

# Geçerli LLM sağlayıcıları (F0-17 adaptör deseni). `anthropic` üretim
# varsayılanıdır; `openai_compat` OpenAI uyumlu /chat/completions sunan her
# sağlayıcıyı kapsar (NVIDIA NIM, Groq, Together, yerel vLLM/Ollama…).
LLM_PROVIDERS: Final[frozenset[str]] = frozenset({"anthropic", "openai_compat"})

# OpenAI uyumlu sunucularda yapılandırılmış çıktının üç ayrı lehçesi var;
# hangisinin desteklendiği modele ve sunucuya göre değişir. Sıra, düşüş
# (downgrade) merdivenidir: soldaki en güçlü garanti.
JSON_MODES: Final[tuple[str, ...]] = ("json_schema", "guided_json", "json_object")

# Geçerli embedding sağlayıcıları (D16). `build_backend` bu kümeyi bilir ama
# doğrulama burada yapılır: hatalı ayar ilk embed çağrısında değil, uygulama
# açılışında görünsün.
EMBEDDING_PROVIDERS: Final[frozenset[str]] = frozenset(
    {"", "hashing", "local", "voyage", "cohere", "openai"}
)

# `.env` tuzağı: `KEY=` (boş değer) satırının sonuna yorum yazılırsa
# python-dotenv yorumu DEĞER sanır ve `PD_EMBEDDING_PROVIDER` değeri
# "# voyage | cohere | ..." olur. Sessizce yanlış yapılandırma yerine
# temizleyip doğruluyoruz.
_INLINE_COMMENT_RE = re.compile(r"\s*#.*$", re.DOTALL)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Uygulama ---
    env: Environment = "development"
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    # --- Altyapı ---
    database_url: str = "postgresql://politikdesk:politikdesk@localhost:5432/politikdesk"
    redis_url: str = "redis://localhost:6379/0"

    # --- LLM (Spec §11.1, §11.5) ---
    # Çıkarım (ucuz model) ile üretim (pahalı model) ayrımı: Risk R6 azaltımı.
    llm_provider: str = "anthropic"
    llm_model_extraction: str = "claude-sonnet-5"
    llm_model_generation: str = "claude-opus-5"

    # `openai_compat` için: uç nokta, anahtarın okunacağı ortam değişkeninin
    # ADI (anahtarın kendisi değil) ve yapılandırılmış çıktı lehçesi.
    llm_base_url: str = ""
    llm_api_key_env: str = ""
    llm_json_mode: str = "json_schema"
    # Akıl yürüten (reasoning) açık modeller tek çağrıda dakikalar sürebilir.
    llm_timeout_seconds: float = Field(default=120.0, gt=0)
    # Geçici 429/503'te toplam deneme sayısı (ücretsiz katmanda gerekli).
    llm_max_retries: int = Field(default=4, ge=1)
    llm_daily_budget_usd: float = Field(default=5.0, gt=0)
    llm_monthly_budget_usd: float = Field(default=100.0, gt=0)

    # ⚠ SPEC SAPMASI (Faz 0'da tespit edildi — bkz. docs/karar-itirazlari.md, İtiraz-3)
    # Spec §11.5 "sıcaklık: çıkarım 0–0.2, üretim 0.6–0.8" diyor. Ancak seçilen
    # model sınıfı (Claude Opus 5 / Sonnet 5) `temperature` parametresini
    # KABUL ETMİYOR — gönderilirse HTTP 400 döner. Sıcaklığın işlevsel karşılığı
    # `output_config.effort`tir. Spec'in amacı (çıkarım deterministik, üretim
    # yaratıcı) effort seviyesiyle korunur.
    llm_effort_extraction: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    llm_effort_generation: Literal["low", "medium", "high", "xhigh", "max"] = "high"

    # Claude Opus 5 güvenlik sınıflandırıcıları bir isteği reddedebilir
    # (HTTP 200 + stop_reason="refusal"). Sunucu tarafı yedeği açık tutulur.
    llm_enable_fallbacks: bool = True

    # --- Embedding (D16 — Faz 0'da benchmark ile seçilir) ---
    embedding_provider: str = ""
    embedding_model: str = ""
    embedding_dim: int = Field(default=1024, description="Şemada VECTOR(1024) sabit")

    # --- Gözlemlenebilirlik (F0-18) ---
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = Field(default=0.1, ge=0, le=1)

    # --- Tek kullanıcı (Faz 3) ---
    # Kimlik doğrulama katmanı yok (kişisel araç kararı); `users` satırı
    # yine de gerekir çünkü drafts/profiles/briefings ona bakıyor.
    user_email: str = "local@politikdesk.local"
    user_display_name: str = "PolitikDesk"

    # --- Brifing (F3-16, F3-17) ---
    # SMTP tanımlı değilse brifing YİNE ÜRETİLİR, yalnızca gönderilmez:
    # e-posta yapılandırması bir dağıtım ayrıntısıdır, üretim koşulu değil.
    briefing_morning_hour: int = Field(default=8, ge=0, le=23)
    briefing_evening_hour: int = Field(default=20, ge=0, le=23)
    briefing_max_events: int = Field(default=7, ge=1, le=20)
    briefing_min_events: int = Field(default=5, ge=1, le=20)
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    # E-postadaki olay/izleme linklerinin mutlak adresi.
    public_base_url: str = "http://localhost:8000"

    # --- Editoryal üretim (F3-10) ---
    # Taslak uzunluğu X gönderisi ölçeğindedir; sınır promptta DA yazılır
    # ama asıl zorlama üretim sonrası kesme değil, şema `maxLength`'idir.
    draft_max_chars: int = Field(default=600, ge=200, le=2000)

    # --- Kümeleme eşikleri (D20 — F2-14 ile kalibre edildi) ---
    # Spec §11.4'ün tahminleri 0,86 / 0,78 idi. Golden Set üzerinde eşik
    # taraması (eval/threshold_report.md) bu değerlerde false merge oranını
    # %10,7 buldu — G2'nin pazarlıksız koşulu (≤ %5) tutmuyordu.
    # 0,92 / 0,88 ile false merge %2,6'ya iniyor, recall %82,4'te kalıyor.
    cluster_t_high: float = Field(default=0.92, ge=0, le=1)
    cluster_t_low: float = Field(default=0.88, ge=0, le=1)

    @field_validator(
        "embedding_provider",
        "embedding_model",
        "llm_provider",
        "llm_base_url",
        "llm_api_key_env",
        "llm_json_mode",
        "llm_model_extraction",
        "llm_model_generation",
        mode="before",
    )
    @classmethod
    def _strip_inline_comment(cls, v: object) -> object:
        if isinstance(v, str):
            return _INLINE_COMMENT_RE.sub("", v).strip()
        return v

    @field_validator("llm_provider")
    @classmethod
    def _llm_provider_must_be_known(cls, v: str) -> str:
        provider = v.strip().lower()
        if provider not in LLM_PROVIDERS:
            raise ValueError(
                f"Bilinmeyen LLM sağlayıcısı: {v!r}. Seçenekler: {sorted(LLM_PROVIDERS)}"
            )
        return provider

    @field_validator("llm_json_mode")
    @classmethod
    def _json_mode_must_be_known(cls, v: str) -> str:
        mode = v.strip().lower()
        if mode not in JSON_MODES:
            raise ValueError(
                f"Bilinmeyen llm_json_mode: {v!r}. Seçenekler: {list(JSON_MODES)}"
            )
        return mode

    @model_validator(mode="after")
    def _openai_compat_needs_endpoint_and_key(self) -> Settings:
        """Eksik yapılandırma ilk LLM çağrısında değil, açılışta görünsün.

        `openai_compat` sağlayıcısında uç nokta ve anahtar değişkeni adı
        zorunludur: varsayılan uydurmak, yanlış sağlayıcıya sessizce istek
        göndermek demektir.
        """
        if self.llm_provider != "openai_compat":
            return self

        missing = [
            name
            for name, value in (
                ("PD_LLM_BASE_URL", self.llm_base_url),
                ("PD_LLM_API_KEY_ENV", self.llm_api_key_env),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                f"llm_provider='openai_compat' için {', '.join(missing)} zorunludur. "
                "Örnek (NVIDIA NIM): PD_LLM_BASE_URL=https://integrate.api.nvidia.com/v1, "
                "PD_LLM_API_KEY_ENV=NVIDIA_API_KEY"
            )
        return self

    @model_validator(mode="after")
    def _briefing_range_is_sane(self) -> Settings:
        if self.briefing_min_events > self.briefing_max_events:
            raise ValueError(
                "PD_BRIEFING_MIN_EVENTS, PD_BRIEFING_MAX_EVENTS'ten büyük olamaz "
                f"({self.briefing_min_events} > {self.briefing_max_events})."
            )
        return self

    @field_validator("embedding_provider")
    @classmethod
    def _provider_must_be_known(cls, v: str) -> str:
        provider = v.strip().lower()
        if provider not in EMBEDDING_PROVIDERS:
            raise ValueError(
                f"Bilinmeyen embedding sağlayıcısı: {v!r}. "
                f"Seçenekler: {sorted(EMBEDDING_PROVIDERS - {''})} "
                f"(boş bırakmak 'hashing' demektir — üretim için uygun değildir)."
            )
        return provider

    @field_validator("embedding_dim")
    @classmethod
    def _dim_must_match_schema(cls, v: int) -> int:
        if v != 1024:
            raise ValueError(
                "embedding_dim 1024 olmalı — migrations/0001_initial.sql "
                "VECTOR(1024) olarak sabitlenmiştir (Spec §11.1)."
            )
        return v

    @field_validator("cluster_t_low")
    @classmethod
    def _low_below_high(cls, v: float, info) -> float:  # noqa: ANN001
        t_high = info.data.get("cluster_t_high")
        if t_high is not None and v >= t_high:
            raise ValueError("cluster_t_low, cluster_t_high'tan küçük olmalı (Spec §11.4).")
        return v

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def load_env_file(path: str | Path = ".env") -> list[str]:
    """`.env`'deki sağlayıcı anahtarlarını sürecin ortamına yükler.

    `Settings` yalnızca `PD_` önekli değişkenleri okur. API anahtarları ise
    sağlayıcının kendi standart adını kullanır (`ANTHROPIC_API_KEY`,
    `NVIDIA_API_KEY`…) ve `os.environ`'a ancak biri koyarsa gelir.
    Docker'da bunu compose'un `env_file`'ı yapıyordu; **yerel koşumda
    kimse yapmıyordu** — anahtar `.env`'e doğru yazılmışken bile
    `LLMNotConfigured` alınıyor, üstelik hata "`.env` dosyasına ekleyin"
    diyerek yanlış yöne gönderiyordu.

    Kabuktan verilen değer `.env`'i yener: var olan değişkenler EZİLMEZ.
    Değerler değil, yalnızca yüklenen değişken ADLARI döner (loglanabilsin).
    """
    env_path = Path(path)
    if not env_path.is_file():
        return []

    from dotenv import dotenv_values

    loaded: list[str] = []
    for key, value in dotenv_values(env_path, encoding="utf-8").items():
        if not value or key in os.environ:
            continue
        os.environ[key] = value
        loaded.append(key)
    return loaded
