"""Sağlayıcı-agnostik LLM adaptörü (F0-17).

Tüm LLM çağrıları buradan geçer (Spec §11.5). Adapter deseni model
kilidini kırar: sağlayıcı değişirse yalnızca `_AnthropicBackend` değişir.

Kullanım:
    client = LLMClient()
    result = client.complete_json(
        purpose="claims",
        prompt_version="claims.v1",
        system=SYSTEM_BLOCK,
        user=user_text,
        schema=CLAIMS_SCHEMA,
        task="extraction",
    )
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from politikdesk.config import Settings, get_settings
from politikdesk.llm.budget import BudgetGuard, CallRecord
from politikdesk.llm.errors import LLMError, LLMRefusal, SchemaValidationError
from politikdesk.llm.pricing import estimate_cost_usd
from politikdesk.observability import get_logger

log = get_logger(__name__)

Task = Literal["extraction", "generation"]

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
    ) -> tuple[str, dict[str, int]]:
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
            import anthropic  # yerel import: anahtar yoksa modül yüklemesi patlamasın

            self._client = anthropic.Anthropic()
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
    ) -> tuple[str, dict[str, int]]:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ],
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
        self.backend = backend or _AnthropicBackend(self.settings)
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


__all__ = ["GROUNDING_INSTRUCTION", "LLMClient", "LLMError", "LLMResult"]
