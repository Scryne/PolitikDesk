"""Sağlayıcı-agnostik LLM adaptörü (F0-17).

Tüm LLM çağrıları buradan geçer (Spec §11.5). Adapter deseni model
kilidini kırar: sağlayıcı değişirse yalnızca `_AnthropicBackend` değişir.

Kullanım:
    client = LLMClient()
    result = client.complete_json(
        purpose="claims",
        prompt_version="claims.v2",
        system=SYSTEM_BLOCK,
        user=user_text,
        schema=CLAIMS_SCHEMA,
        task="extraction",
    )
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypedDict

from politikdesk.config import JSON_MODES, Settings, get_settings
from politikdesk.llm.budget import BudgetGuard, CallRecord
from politikdesk.llm.errors import (
    LLMError,
    LLMHTTPError,
    LLMNotConfigured,
    LLMRefusal,
    SchemaValidationError,
)
from politikdesk.llm.pricing import estimate_cost_usd
from politikdesk.observability import get_logger

log = get_logger(__name__)

Task = Literal["extraction", "generation"]


class TokenUsage(TypedDict):
    """Bir çağrının token muhasebesi.

    `dict[str, int]` yerine TypedDict: bu sözlük `estimate_cost_usd(**usage)`
    ve `CallRecord(**usage)` çağrılarına açılıyor; anahtar adı kayarsa hata
    çalışma anında değil tip denetiminde görünsün (B-40).
    """

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int


# Spec §11.5 — grounding kuralı. Her üretim/özetleme promptuna eklenir.
GROUNDING_INSTRUCTION = (
    "Yalnızca sana verilen kanıt listesindeki bilgiyi kullan. "
    "Kanıtta olmayan hiçbir olgu, sayı, tarih veya alıntı ekleme. "
    "Bir bilgi kanıtta yoksa 'kanıt yok' yaz."
)


@dataclass(frozen=True)
class LLMResult:
    """Bir LLM çağrısının sonucu ve muhasebesi."""

    data: dict[str, Any]
    raw_text: str
    model: str
    prompt_version: str | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: float
    latency_ms: int


class Backend(Protocol):
    """Sağlayıcı arka ucu. Testlerde sahte (fake) uygulama kullanılır."""

    def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        effort: str,
        max_tokens: int,
    ) -> tuple[str, TokenUsage]:
        """(metin, kullanım) döndürür. Kullanım anahtarları:
        input_tokens, output_tokens, cache_read_tokens, cache_write_tokens.
        """
        ...


class _AnthropicBackend:
    """Anthropic Claude arka ucu.

    Model sınıfı notları (Faz 0'da doğrulandı):
      * `temperature` / `top_p` / `top_k` KABUL EDİLMEZ (HTTP 400).
        Derinlik kontrolü `output_config.effort` ile yapılır.
      * Yapılandırılmış çıktı `output_config.format` ile zorlanır.
      * Güvenlik sınıflandırıcısı isteği reddedebilir: HTTP 200 +
        stop_reason="refusal". Bu `LLMRefusal` olarak yükseltilir.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                # SDK bu durumda ham bir TypeError fırlatıyor ("Could not
                # resolve authentication method..."), sebebi görünmüyordu.
                raise LLMNotConfigured("ANTHROPIC_API_KEY")

            import anthropic  # yerel import: anahtar yoksa modül yüklemesi patlamasın

            self._client = anthropic.Anthropic(
                max_retries=self._settings.llm_max_retries,
                timeout=float(self._settings.llm_timeout_seconds),
            )
        return self._client

    def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        effort: str,
        max_tokens: int,
    ) -> tuple[str, TokenUsage]:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": user}],
            "output_config": {
                "effort": effort,
                "format": {"type": "json_schema", "schema": schema},
            },
        }

        if self._settings.llm_enable_fallbacks:
            # Reddedilen istek sessizce durmasın: sunucu tarafı yedek modele düşsün.
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["fallbacks"] = "default"
            response = self.client.beta.messages.create(**kwargs)
        else:
            response = self.client.messages.create(**kwargs)

        if getattr(response, "stop_reason", None) == "refusal":
            details = getattr(response, "stop_details", None)
            raise LLMRefusal(
                category=getattr(details, "category", None),
                explanation=getattr(details, "explanation", None),
            )

        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        usage = response.usage
        return text, {
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        }


# Modelin akıl yürütmesini çıktıya sızdırdığı iki yaygın biçim. Açık
# modellerde (Qwen, DeepSeek, Nemotron) JSON'un önüne bunlar gelir ve
# `json.loads` patlar; sağlayıcıya özgü olduğu için arka uçta temizlenir.
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(?P<body>.*?)\s*```\s*$", re.DOTALL)

# effort -> temperature. Spec §11.5'in ÖZGÜN kuralı ("çıkarım 0–0.2,
# üretim 0.6–0.8") burada geri gelir: sıcaklığı reddeden Claude sınıfı
# için yapılan sapma (İtiraz-3) OpenAI uyumlu arka uçta geçerli değildir.
_TEMPERATURE_BY_EFFORT: dict[str, float] = {
    "low": 0.0,
    "medium": 0.3,
    "high": 0.7,
    "xhigh": 0.7,
    "max": 0.8,
}

# Geçici sunucu durumları. Ücretsiz katmanda 503 "ResourceExhausted:
# Worker local total request limit reached" canlı koşumda gerçekten
# görüldü — yeniden denemeyen boru hattı bunu makale kaybı olarak yazar.
# `ingestion/http.py` ile aynı deyim: üstel geri çekilme + Retry-After.
_RETRYABLE_STATUS: frozenset[int] = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
_MAX_BACKOFF_S: float = 30.0


def _retry_after_seconds(response: Any) -> float | None:
    """`Retry-After` başlığı varsa ona uy — tahmin etmekten iyidir."""
    raw = response.headers.get("retry-after") if response.headers else None
    if not raw:
        return None
    try:
        return min(float(raw), 120.0)
    except ValueError:
        return None


class _OpenAICompatBackend:
    """OpenAI uyumlu `/chat/completions` arka ucu.

    NVIDIA NIM (build.nvidia.com), Groq, Together, yerel vLLM/Ollama —
    hepsi aynı sözleşmeyi konuşur. `anthropic` SDK'sı yerine düz `httpx`
    kullanılır: bağımlılık zaten var ve sözleşme tek uç noktadan ibaret.

    İki sağlayıcı farkı burada soğurulur, üst katmana sızmaz:
      * Yapılandırılmış çıktının üç lehçesi (`json_schema` / NVIDIA'ya
        özgü `nvext.guided_json` / kaba `json_object`). Sunucu birini 400
        ile reddederse bir alt basamağa DÜŞÜLÜR ve bu uyarı olarak
        loglanır — sessiz davranış değişikliği değildir.
      * `effort` parametresi yoktur; sıcaklığa çevrilir.
    """

    def __init__(self, settings: Settings, http: Any = None) -> None:
        self._settings = settings
        self._http = http
        self._mode = settings.llm_json_mode

    # -- altyapı -------------------------------------------------------------
    @property
    def http(self) -> Any:
        if self._http is None:
            import httpx  # yerel import: anahtar yoksa kurulum patlamasın

            self._http = httpx.Client(timeout=self._settings.llm_timeout_seconds)
        return self._http

    def _api_key(self) -> str:
        var = self._settings.llm_api_key_env
        key = os.environ.get(var)
        if not key:
            from politikdesk.config import load_env_file

            load_env_file()
            key = os.environ.get(var)
        if not key:
            raise LLMNotConfigured(var)
        return key

    def _post_with_retry(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> Any:
        """Geçici sunucu hatalarında üstel geri çekilmeyle yeniden dener.

        Yalnızca GEÇİCİ durumlar yeniden denenir. 400/404/422 lehçe
        sorunudur ve tekrar denemek düzeltmez — onları çağıran katmandaki
        düşüş merdiveni ele alır.

        D03 düzeltmesi: tüm denemeler tükendiğinde artık başarısız yanıt
        döndürülmez, `LLMHTTPError` fırlatılır. Eski davranış çağıranın
        durum kodunu yeniden kontrol etmesine bağlıydı; yeni çağıranlar
        bu sözleşmeyi bilmeden hatalı yanıtı geçerli sayabilirdi.
        """
        attempts = max(self._settings.llm_max_retries, 1)
        response: Any = None

        for attempt in range(attempts):
            response = self.http.post(url, headers=headers, json=payload)
            if response.status_code not in _RETRYABLE_STATUS:
                return response
            if attempt == attempts - 1:
                break

            delay = _retry_after_seconds(response)
            if delay is None:
                delay = min(2.0**attempt, _MAX_BACKOFF_S)
            log.warning(
                "llm_backoff",
                model=payload.get("model"),
                attempt=attempt + 1,
                status=response.status_code,
                sleep_s=round(delay, 2),
                detail=response.text[:160],
            )
            time.sleep(delay)

        # D03: tüm denemeler tükendi — başarısız yanıtı sessizce döndürme.
        assert response is not None
        raise LLMHTTPError(response.status_code, response.text, url)

    # -- istek gövdesi -------------------------------------------------------
    def _payload(
        self,
        *,
        mode: str,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        effort: str,
        max_tokens: int,
    ) -> dict[str, Any]:
        system_text = system
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": _TEMPERATURE_BY_EFFORT.get(effort, 0.0),
            "stream": False,
        }

        if mode == "json_schema":
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "politikdesk_output",
                    "strict": True,
                    "schema": schema,
                },
            }
        elif mode == "guided_json":
            body["nvext"] = {"guided_json": schema}
        else:  # json_object — sunucu şemayı zorlayamaz, prompta yazılır
            body["response_format"] = {"type": "json_object"}
            system_text = (
                f"{system}\n\nÇIKTI BİÇİMİ: yalnızca şu JSON şemasına uyan tek bir "
                f"JSON nesnesi döndür. Açıklama, markdown veya kod bloğu ekleme.\n"
                f"{json.dumps(schema, ensure_ascii=False)}"
            )

        body["messages"] = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user},
        ]
        return body

    # -- yanıt ---------------------------------------------------------------
    @staticmethod
    def _clean(text: str) -> str:
        """Modelin JSON'un etrafına eklediği kabuğu soyar."""
        text = _THINK_BLOCK_RE.sub("", text)
        # Kapanmamış düşünce bloğu: son `</think>`ten sonrası cevaptır.
        if "</think>" in text:
            text = text.rsplit("</think>", 1)[1]
        fenced = _CODE_FENCE_RE.match(text)
        if fenced:
            text = fenced.group("body")
        return text.strip()

    @staticmethod
    def _usage(raw: dict[str, Any]) -> TokenUsage:
        usage = raw.get("usage") or {}
        details = usage.get("prompt_tokens_details") or {}
        cached = int(details.get("cached_tokens") or 0)
        return {
            # prompt_tokens önbellekten okunanı DA içerir; iki kez saymamak
            # için ayrıştırılır (Anthropic muhasebesiyle aynı anlam).
            "input_tokens": max(int(usage.get("prompt_tokens") or 0) - cached, 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
            "cache_read_tokens": cached,
            "cache_write_tokens": 0,
        }

    def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        effort: str,
        max_tokens: int,
    ) -> tuple[str, TokenUsage]:
        key = self._api_key()
        url = self._settings.llm_base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

        # Merdiven: yapılandırılmış mevcut moddan başlar, aşağı iner.
        ladder = list(JSON_MODES[JSON_MODES.index(self._mode) :])
        last_error: LLMHTTPError | None = None

        for mode in ladder:
            payload = self._payload(
                mode=mode,
                model=model,
                system=system,
                user=user,
                schema=schema,
                effort=effort,
                max_tokens=max_tokens,
            )
            response = self._post_with_retry(url, headers, payload)

            # 404 KASITLI OLARAK yok: "model bu hesaba açık değil" bir lehçe
            # sorunu değildir ve merdiven tırmanmak yalnızca iki çağrı israf
            # eder. Desteklenmeyen parametre 400/422 döner.
            if response.status_code in (400, 422):
                last_error = LLMHTTPError(response.status_code, response.text, url)
                if mode == ladder[-1]:
                    raise last_error
                log.warning(
                    "llm_json_mode_downgraded",
                    model=model,
                    tried=mode,
                    status=response.status_code,
                    detail=response.text[:200],
                )
                continue

            if response.status_code >= 400:
                raise LLMHTTPError(response.status_code, response.text, url)

            if mode != self._mode:
                # Çalışan mod hatırlanır; her çağrıda merdiveni baştan
                # tırmanmak çağrı başına boşa istek demektir.
                self._mode = mode

            data = response.json()
            choice = (data.get("choices") or [{}])[0]

            if choice.get("finish_reason") == "content_filter":
                raise LLMRefusal(category="content_filter", explanation=None)

            message = choice.get("message") or {}
            text = self._clean(message.get("content") or "")
            if not text:
                raise SchemaValidationError(
                    f"Model boş içerik döndürdü (model={model}, "
                    f"finish_reason={choice.get('finish_reason')!r})."
                )
            return text, self._usage(data)

        raise last_error or LLMHTTPError(0, "bilinmeyen hata", url)


def build_backend(settings: Settings) -> Backend:
    """Ayarlara göre arka ucu seçer (F0-17 adaptör deseni).

    Model kilidini kıran nokta burasıdır: sağlayıcı değişimi tek satırlık
    yapılandırma, kod değişikliği değil.
    """
    if settings.llm_provider == "openai_compat":
        return _OpenAICompatBackend(settings)
    return _AnthropicBackend(settings)


class LLMClient:
    """Bütçe korumalı, muhasebeli, yapılandırılmış-çıktı zorunlu istemci."""

    def __init__(
        self,
        *,
        backend: Backend | None = None,
        guard: BudgetGuard | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.backend = backend or build_backend(self.settings)
        self.guard = guard or BudgetGuard(settings=self.settings)

    def _model_for(self, task: Task) -> str:
        return (
            self.settings.llm_model_extraction
            if task == "extraction"
            else self.settings.llm_model_generation
        )

    def _effort_for(self, task: Task) -> str:
        return (
            self.settings.llm_effort_extraction
            if task == "extraction"
            else self.settings.llm_effort_generation
        )

    def complete_json(
        self,
        *,
        purpose: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        task: Task = "extraction",
        prompt_version: str | None = None,
        model: str | None = None,
        max_tokens: int = 8000,
        user_id: int | None = None,
    ) -> LLMResult:
        """Yapılandırılmış JSON çıktı üretir; maliyeti kaydeder.

        Bütçe tavanı aşılırsa çağrı YAPILMAZ — `BudgetExceeded` fırlatılır.
        """
        model = model or self._model_for(task)
        effort = self._effort_for(task)

        self.guard.check()

        started = time.perf_counter()
        try:
            text, usage = self.backend.complete_json(
                model=model,
                system=system,
                user=user,
                schema=schema,
                effort=effort,
                max_tokens=max_tokens,
            )
        except LLMNotConfigured:
            # Çağrı hiç yapılmadı; harcama defterine başarısız çağrı yazmak
            # `llm_calls` tablosunu yanıltır.
            raise
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            self.guard.record(
                CallRecord(
                    purpose=purpose,
                    model=model,
                    prompt_version=prompt_version,
                    latency_ms=latency_ms,
                    user_id=user_id,
                    succeeded=False,
                    error_type=type(exc).__name__,
                )
            )
            raise

        latency_ms = int((time.perf_counter() - started) * 1000)
        cost = estimate_cost_usd(model, **usage)

        self.guard.record(
            CallRecord(
                purpose=purpose,
                model=model,
                prompt_version=prompt_version,
                cost_usd=cost,
                latency_ms=latency_ms,
                user_id=user_id,
                **usage,
            )
        )

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            # Yedek ayıklayıcı: metin içinde { ... } bloğu ara
            # (açık modellerin çevre metinleri için)
            first_brace = text.find("{")
            last_brace = text.rfind("}")
            if first_brace != -1 and last_brace > first_brace:
                try:
                    data = json.loads(text[first_brace : last_brace + 1])
                except json.JSONDecodeError:
                    raise SchemaValidationError(
                        f"Model çıktısı geçerli JSON değil (purpose={purpose}, model={model})."
                    ) from exc
            else:
                raise SchemaValidationError(
                    f"Model çıktısı geçerli JSON değil (purpose={purpose}, model={model})."
                ) from exc

        if not isinstance(data, dict):
            raise SchemaValidationError(
                f"Model çıktısı bir JSON nesnesi değil (purpose={purpose})."
            )

        return LLMResult(
            data=data,
            raw_text=text,
            model=model,
            prompt_version=prompt_version,
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            cache_read_tokens=usage["cache_read_tokens"],
            cost_usd=cost,
            latency_ms=latency_ms,
        )


__all__ = [
    "GROUNDING_INSTRUCTION",
    "LLMClient",
    "LLMError",
    "LLMResult",
    "build_backend",
]
