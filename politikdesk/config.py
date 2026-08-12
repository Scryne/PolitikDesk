"""Uygulama ayarları — tek kaynak (F0-12).

Tüm ayarlar `PD_` önekli ortam değişkenlerinden okunur; API anahtarları
sağlayıcının kendi standart değişken adını kullanır (ANTHROPIC_API_KEY vb.).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]


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
    llm_model_extraction: str = "claude-sonnet-5"
    llm_model_generation: str = "claude-opus-5"
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

    # --- Kümeleme eşikleri (D20 — F2-14 ile kalibre edildi) ---
    # Spec §11.4'ün tahminleri 0,86 / 0,78 idi. Golden Set üzerinde eşik
    # taraması (eval/threshold_report.md) bu değerlerde false merge oranını
    # %10,7 buldu — G2'nin pazarlıksız koşulu (≤ %5) tutmuyordu.
    # 0,92 / 0,88 ile false merge %2,6'ya iniyor, recall %82,4'te kalıyor.
    cluster_t_high: float = Field(default=0.92, ge=0, le=1)
    cluster_t_low: float = Field(default=0.88, ge=0, le=1)

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
