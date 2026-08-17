"""Uygulama ayarları — tek kaynak (F0-12).

Tüm ayarlar `PD_` önekli ortam değişkenlerinden okunur; API anahtarları
sağlayıcının kendi standart değişken adını kullanır (ANTHROPIC_API_KEY vb.).
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, Literal

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
_INLINE_COMMENT_RE = re.compile(r"\s*#.*$", re.DOTALL)

_OPTIONAL_EMPTY_STRING_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "git_sha",
        "git_branch",
        "build_timestamp",
        "image_digest",
        "deployed_at",
        "api_token",
        "llm_base_url",
        "llm_api_key_env",
        "embedding_provider",
        "embedding_model",
        "sentry_dsn",
        "smtp_host",
        "smtp_user",
        "smtp_password",
        "smtp_from",
    }
)


def resolve_env_file_path(custom: str | Path | None = None) -> Path | None:
    """Güvenli `.env` dosya yolunu belirler (B-88, S0-2).

    Öncelik sırası:
      1. Parametre olarak verilen yol (varsa)
      2. PD_ENV_FILE ortam değişkeni (varsa)
      3. Windows: %LOCALAPPDATA%\\PolitikDesk\\.env (bulut eşitlemesi dışı)
      4. Linux/macOS: ~/.config/politikdesk/.env
      5. Geriye uyumluluk: Çalışma dizinindeki .env
    """
    if custom is not None:
        p = Path(custom)
        if p.is_file():
            return p

    env_var = os.environ.get("PD_ENV_FILE")
    if env_var:
        p = Path(env_var)
        if p.is_file():
            return p

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        p = Path(local_appdata) / "PolitikDesk" / ".env"
        if p.is_file():
            return p

    home_config = Path.home() / ".config" / "politikdesk" / ".env"
    if home_config.is_file():
        return home_config

    local_env = Path(".env")
    if local_env.is_file():
        return local_env

    return None


_resolved_env_file = resolve_env_file_path()

# D01 düzeltmesi: `.env` bulut eşitlemesi altındaysa uyar. API anahtarları
# ve SMTP parolası bu dosyada tutulur; OneDrive/Dropbox altında olması
# tüm sırları üçüncü tarafa kopyalar (bkz. backup_policy.py B-84 analizi).
if _resolved_env_file is not None:
    try:
        from politikdesk.backup_policy import cloud_sync_reason as _cloud_check

        _cloud_reason = _cloud_check(_resolved_env_file)
        if _cloud_reason:
            import warnings

            warnings.warn(
                f".env dosyası bulut eşitlemesi altında: {_resolved_env_file}\n"
                f"  Sebep: {_cloud_reason}\n"
                "  API anahtarları ve parolalar bulut sağlayıcısına kopyalanıyor.\n"
                "  Çözüm: .env dosyasını bulut dışına taşıyın, örneğin:\n"
                "    Windows: %LOCALAPPDATA%\\PolitikDesk\\.env\n"
                "    Linux:   ~/.config/politikdesk/.env\n"
                "  veya PD_ENV_FILE ortam değişkeniyle yol belirtin.",
                UserWarning,
                stacklevel=1,
            )
    except Exception:  # noqa: BLE001 — uyarı altyapısı açılışı kırmamalı
        pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PD_",
        env_file=str(_resolved_env_file) if _resolved_env_file else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Uygulama ---
    env: Environment = "development"
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"
    timezone: str = "Europe/Istanbul"

    # --- Release Kimliği (F1) ---
    git_sha: str = ""
    git_branch: str = ""
    build_timestamp: str = ""
    image_digest: str = ""
    deployed_at: str = ""

    # --- Kimlik doğrulama (I01 — denetim düzeltmesi) ---
    # Ayarlanmışsa tüm uçlar (sağlık hariç) bu belirteci gerektirir.
    # Boşsa kimlik doğrulama atlanır — geliştirme ortamında geriye uyumlu.
    api_token: str = ""

    # --- Altyapı ---
    # `localhost` DEĞİL, `127.0.0.1`. F4-09'da yayımlanan portlar güvenlik
    # gerekçesiyle loopback'e bağlandı (`127.0.0.1:5432:5432`) ve Docker
    # yalnızca IPv4 loopback'i dinliyor. Windows'ta `localhost` önce
    # `::1`e çözümlenir; oradan bağlantı reddedilir ve ana makinede koşan
    # araçlar (pytest, `pd backup`, `pd pipeline-health`) havuz zaman
    # aşımına düşer. Konteynerler bu değeri kullanmaz — compose onlara
    # `db:5432` / `redis:6379` verir.
    database_url: str = "postgresql://politikdesk:politikdesk@127.0.0.1:5432/politikdesk"
    redis_url: str = "redis://127.0.0.1:6379/0"
    db_pool_min: int = Field(default=1, ge=0)
    db_pool_max: int = Field(default=10, ge=1, le=100)

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

    @model_validator(mode="before")
    @classmethod
    def _ignore_empty_string_env_values(cls, data: Any) -> Any:
        """Ortam değişkeni boşluk veya "" olarak verildiğinde varsayılan değere dön.

        Vercel veya .env şablonlarında değişkenler boş bırakıldığında
        (örn: `PD_LOG_FORMAT=` veya `PD_LLM_DAILY_BUDGET_USD=`) Pydantic'in
        int/float/Literal alanlarda ValidationError fırlatmasını önler.
        """
        if isinstance(data, dict):
            cleaned: dict[str, Any] = {}
            for key, value in data.items():
                if (
                    isinstance(value, str)
                    and value.strip() == ""
                    and key not in _OPTIONAL_EMPTY_STRING_FIELDS
                ):
                    continue
                cleaned[key] = value
            return cleaned
        return data

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
            raise ValueError(f"Bilinmeyen llm_json_mode: {v!r}. Seçenekler: {list(JSON_MODES)}")
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
    def _production_requires_api_token(self) -> Settings:
        """Üretim ortamında api_token zorunludur.

        Token ayarlanmamışsa kimlik doğrulama atlanır; üretim ortamında bu durum
        tüm API ve yönetim uçlarını açıkta bırakır.
        """
        if self.is_production and not self.api_token:
            raise ValueError(
                "PD_ENV='production' iken PD_API_TOKEN zorunludur. "
                "API ve admin uçlarını korumak için güvenli bir belirteç tanımlayın."
            )
        return self

    @model_validator(mode="after")
    def _db_pool_range_is_sane(self) -> Settings:
        if self.db_pool_min > self.db_pool_max:
            raise ValueError(
                f"PD_DB_POOL_MIN ({self.db_pool_min}), "
                f"PD_DB_POOL_MAX'ten ({self.db_pool_max}) büyük olamaz."
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
    load_env_file()
    return Settings()



def load_env_file(path: str | Path | None = None) -> list[str]:
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
    env_path = Path(path) if path is not None else resolve_env_file_path()
    if not env_path or not env_path.is_file():
        return []

    from dotenv import dotenv_values

    loaded: list[str] = []
    for key, value in dotenv_values(env_path, encoding="utf-8").items():
        if not value or key in os.environ:
            continue
        os.environ[key] = value
        loaded.append(key)
    return loaded
