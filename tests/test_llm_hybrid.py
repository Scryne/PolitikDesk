"""Hibrit LLM Mimarisi Testleri (Yerel Ollama + Bulut NVIDIA NIM).

Görev bazlı yönlendirme (extraction -> yerel, generation -> bulut),
akıllı fallback mekanizması ve maliyet muhasebesi test edilir.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from politikdesk.config import Settings
from politikdesk.llm.budget import BudgetGuard, InMemoryLedger
from politikdesk.llm.client import (
    LLMClient,
    _OpenAICompatBackend,
    build_backend,
)
from politikdesk.llm.errors import LLMHTTPError
from politikdesk.llm.pricing import estimate_cost_usd

EXTRACTION_MODEL = "qwen2.5:7b-instruct-q5_K_M"
GENERATION_MODEL = "meta/llama-3.3-70b-instruct"
SCHEMA = {"type": "object", "properties": {"claims": {"type": "array"}}}


def _hybrid_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "env": "test",
        "llm_provider": "hybrid",
        "llm_extraction_base_url": "http://127.0.0.1:11434/v1",
        "llm_extraction_api_key_env": "",
        "llm_model_extraction": EXTRACTION_MODEL,
        "llm_extraction_json_mode": "json_object",
        "llm_generation_base_url": "https://integrate.api.nvidia.com/v1",
        "llm_generation_api_key_env": "NVIDIA_API_KEY",
        "llm_model_generation": GENERATION_MODEL,
        "llm_generation_json_mode": "json_schema",
        "llm_fallback_enabled": True,
    }
    base.update(overrides)
    return Settings(**base)


# ------------------------------------------------------------- 1. Yapılandırma Doğrulama
def test_hybrid_settings_validation_missing_urls() -> None:
    """Hibrit modda extraction veya generation URL eksikse açılışta hata fırlatılmalı."""
    with pytest.raises(ValueError, match="PD_LLM_EXTRACTION_BASE_URL"):
        Settings(
            env="test",
            llm_provider="hybrid",
            llm_base_url="",
            llm_extraction_base_url="",
            llm_generation_base_url="https://integrate.api.nvidia.com/v1",
            llm_generation_api_key_env="NVIDIA_API_KEY",
        )

    with pytest.raises(ValueError, match="PD_LLM_GENERATION_BASE_URL"):
        Settings(
            env="test",
            llm_provider="hybrid",
            llm_base_url="",
            llm_extraction_base_url="http://127.0.0.1:11434/v1",
            llm_generation_base_url="",
        )


def test_hybrid_settings_remote_requires_api_key() -> None:
    """Yerel olmayan bir uç nokta için API_KEY_ENV zorunludur."""
    with pytest.raises(ValueError, match="PD_LLM_GENERATION_API_KEY_ENV"):
        Settings(
            env="test",
            llm_provider="hybrid",
            llm_base_url="",
            llm_api_key_env="",
            llm_extraction_base_url="http://127.0.0.1:11434/v1",
            llm_generation_base_url="https://integrate.api.nvidia.com/v1",
            llm_generation_api_key_env="",
        )


def test_build_backend_hybrid_selection() -> None:
    """build_backend, görev tipine göre doğru uç noktayı seçmeli."""
    settings = _hybrid_settings()
    ext_backend = build_backend(settings, task="extraction")
    gen_backend = build_backend(settings, task="generation")

    assert isinstance(ext_backend, _OpenAICompatBackend)
    assert isinstance(gen_backend, _OpenAICompatBackend)
    assert ext_backend._base_url == "http://127.0.0.1:11434/v1"
    assert gen_backend._base_url == "https://integrate.api.nvidia.com/v1"
    assert ext_backend._mode == "json_object"
    assert gen_backend._mode == "json_schema"


# ------------------------------------------------------------- 2. Görev Bazlı Yönlendirme
def test_hybrid_routes_extraction_and_generation() -> None:
    """Extraction yerel backend'e, generation ise bulut backend'e gitmeli."""
    settings = _hybrid_settings()
    sent_requests: list[dict[str, Any]] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        body = json.loads(request.content)
        sent_requests.append({"url": url_str, "body": body})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"claims": []}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )

    http = httpx.Client(transport=httpx.MockTransport(_capture))

    client = LLMClient(
        settings=settings,
        guard=BudgetGuard(ledger=InMemoryLedger(), settings=settings),
    )
    # Mock http client enjekte et
    client._extraction_backend._http = http
    client._generation_backend._http = http

    # 1. Extraction çağrısı (Yerel Ollama)
    res_ext = client.complete_json(
        purpose="claims_extract",
        system="Sistem talimatı",
        user="Haber metni",
        schema=SCHEMA,
        task="extraction",
    )
    assert res_ext.model == EXTRACTION_MODEL
    assert "127.0.0.1:11434" in sent_requests[0]["url"]
    assert sent_requests[0]["body"]["model"] == EXTRACTION_MODEL

    # 2. Generation çağrısı (NVIDIA NIM)
    res_gen = client.complete_json(
        purpose="draft_generate",
        system="Editoryal sistem",
        user="Kanıtlar",
        schema=SCHEMA,
        task="generation",
    )
    assert res_gen.model == GENERATION_MODEL
    assert "integrate.api.nvidia.com" in sent_requests[1]["url"]
    assert sent_requests[1]["body"]["model"] == GENERATION_MODEL


# ------------------------------------------------------------- 3. Akıllı Fallback Mekanizması
def test_hybrid_fallback_on_extraction_failure() -> None:
    """Yerel Ollama çökerse (503/400 vb.) çıkarma işlemi otomatik olarak NVIDIA NIM'e düşmeli."""
    settings = _hybrid_settings(llm_max_retries=1)
    call_log: list[str] = []

    def _ext_handler(request: httpx.Request) -> httpx.Response:
        call_log.append("extraction_failed")
        return httpx.Response(503, text="Ollama offline / GPU out of memory")

    def _gen_handler(request: httpx.Request) -> httpx.Response:
        call_log.append("generation_fallback_success")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": '{"claims": [{"claim_text": "yedek"}]}'},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 150, "completion_tokens": 30},
            },
        )

    client = LLMClient(
        settings=settings,
        guard=BudgetGuard(ledger=InMemoryLedger(), settings=settings),
    )
    client._extraction_backend._http = httpx.Client(
        transport=httpx.MockTransport(_ext_handler), timeout=5.0
    )
    client._generation_backend._http = httpx.Client(
        transport=httpx.MockTransport(_gen_handler), timeout=5.0
    )

    result = client.complete_json(
        purpose="claims_extract",
        system="Sistem",
        user="Metin",
        schema=SCHEMA,
        task="extraction",
    )

    # İki çağrı yapılmış olmalı: önce yerel (başarısız), sonra bulut (başarılı)
    assert call_log == ["extraction_failed", "generation_fallback_success"]
    assert result.model == GENERATION_MODEL
    assert result.data["claims"][0]["claim_text"] == "yedek"


def test_hybrid_fallback_on_generation_failure() -> None:
    """NVIDIA NIM çökerse (429/503) üretim işlemi otomatik olarak yerel Ollama'ya düşmeli."""
    settings = _hybrid_settings(llm_max_retries=1)
    call_log: list[str] = []

    def _gen_handler(request: httpx.Request) -> httpx.Response:
        call_log.append("generation_rate_limited")
        return httpx.Response(429, text="Rate limit exceeded")

    def _ext_handler(request: httpx.Request) -> httpx.Response:
        call_log.append("extraction_fallback_success")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": '{"claims": [{"claim_text": "yerel_yedek"}]}'},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 120, "completion_tokens": 40},
            },
        )

    client = LLMClient(
        settings=settings,
        guard=BudgetGuard(ledger=InMemoryLedger(), settings=settings),
    )
    client._generation_backend._http = httpx.Client(
        transport=httpx.MockTransport(_gen_handler), timeout=5.0
    )
    client._extraction_backend._http = httpx.Client(
        transport=httpx.MockTransport(_ext_handler), timeout=5.0
    )

    result = client.complete_json(
        purpose="draft_generate",
        system="Sistem",
        user="Metin",
        schema=SCHEMA,
        task="generation",
    )

    assert call_log == ["generation_rate_limited", "extraction_fallback_success"]
    assert result.model == EXTRACTION_MODEL
    assert result.data["claims"][0]["claim_text"] == "yerel_yedek"


def test_hybrid_both_fail_raises_and_records_failure() -> None:
    """Hem birincil hem yedek çökerse hata yükseltilmeli ve başarısızlık muhasebeye yazılmalı."""
    settings = _hybrid_settings(llm_max_retries=1)
    ledger = InMemoryLedger()
    guard = BudgetGuard(ledger=ledger, settings=settings)

    def _fail_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = LLMClient(settings=settings, guard=guard)
    client._extraction_backend._http = httpx.Client(
        transport=httpx.MockTransport(_fail_handler), timeout=5.0
    )
    client._generation_backend._http = httpx.Client(
        transport=httpx.MockTransport(_fail_handler), timeout=5.0
    )

    with pytest.raises(LLMHTTPError):
        client.complete_json(
            purpose="claims_extract",
            system="Sistem",
            user="Metin",
            schema=SCHEMA,
            task="extraction",
        )

    assert len(ledger.calls) == 1
    assert ledger.calls[0].succeeded is False
    assert ledger.calls[0].error_type == "LLMHTTPError"


# ------------------------------------------------------------- 4. Maliyet & Fiyatlandırma
def test_local_model_pricing_is_free() -> None:
    """Yerel Ollama modellerinin maliyeti kesinlikle $0.0 olmalı."""
    assert estimate_cost_usd("qwen2.5:7b-instruct-q5_K_M", input_tokens=5000, output_tokens=1000) == 0.0
    assert estimate_cost_usd("qwen2.5:14b-instruct", input_tokens=5000, output_tokens=1000) == 0.0
    assert estimate_cost_usd("meta/llama-3.3-70b-instruct", input_tokens=5000, output_tokens=1000) == 0.0
