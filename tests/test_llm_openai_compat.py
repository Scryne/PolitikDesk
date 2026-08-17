"""OpenAI uyumlu LLM arka ucu (F0-17 adaptör deseni, B-58).

Bu arka uç, `Backend` protokolünün ikinci uygulamasıdır: sağlayıcı
değişiminin gerçekten tek satırlık yapılandırma olduğunun kanıtı.
Testler ağ kullanmaz — `httpx.MockTransport` ile sahte sunucu kurulur.
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
    _AnthropicBackend,
    _OpenAICompatBackend,
    build_backend,
)
from politikdesk.llm.errors import (
    LLMHTTPError,
    LLMNotConfigured,
    LLMRefusal,
    SchemaValidationError,
)

MODEL = "meta/llama-3.3-70b-instruct"
SCHEMA = {"type": "object", "properties": {"claims": {"type": "array"}}}


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "env": "test",
        "llm_provider": "openai_compat",
        "llm_base_url": "https://sahte.ornek/v1",
        "llm_api_key_env": "TEST_LLM_KEY",
        "llm_model_extraction": MODEL,
        "llm_model_generation": MODEL,
    }
    base.update(overrides)
    return Settings(**base)


def _backend(
    handler: Any, settings: Settings | None = None
) -> tuple[_OpenAICompatBackend, list[dict[str, Any]]]:
    """Sahte sunucuya bağlı arka uç ve gönderilen gövdelerin kaydı."""
    sent: list[dict[str, Any]] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return handler(request, len(sent) - 1)

    http = httpx.Client(transport=httpx.MockTransport(_capture))
    return _OpenAICompatBackend(settings or _settings(), http=http), sent


def _ok(body: str = '{"claims": []}', **extra: Any) -> Any:
    payload: dict[str, Any] = {
        "choices": [{"message": {"content": body}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 200},
    }
    payload.update(extra)
    return lambda _request, _n: httpx.Response(200, json=payload)


def _call(backend: _OpenAICompatBackend, **overrides: Any) -> tuple[str, Any]:
    kwargs: dict[str, Any] = {
        "model": MODEL,
        "system": "sistem",
        "user": "kullanici",
        "schema": SCHEMA,
        "effort": "low",
        "max_tokens": 4000,
    }
    kwargs.update(overrides)
    return backend.complete_json(**kwargs)


# ------------------------------------------------------------- seçim
def test_provider_setting_selects_the_backend() -> None:
    """Sağlayıcı değişimi kod değil yapılandırma olmalı."""
    assert isinstance(build_backend(_settings()), _OpenAICompatBackend)
    assert isinstance(
        build_backend(Settings(env="test", llm_provider="anthropic")),
        _AnthropicBackend,
    )


def test_openai_compat_requires_endpoint_and_key_variable() -> None:
    """Eksik yapılandırma ilk çağrıda değil, Settings kurulurken görünsün (DEF-04)."""
    # 1. Boş base_url her durumda PD_LLM_BASE_URL hatası vermeli
    with pytest.raises(ValueError, match="PD_LLM_BASE_URL"):
        Settings(env="test", llm_provider="openai_compat", llm_base_url="", llm_api_key_env="X")
    with pytest.raises(ValueError, match="PD_LLM_BASE_URL"):
        Settings(env="test", llm_provider="openai_compat", llm_base_url="", llm_api_key_env="")

    # 2. Yerel uç noktası (Ollama/vLLM) API key env olmadan geçerli olmalı
    s_local = Settings(
        env="test",
        llm_provider="openai_compat",
        llm_base_url="http://127.0.0.1:11434/v1",
        llm_api_key_env="",
    )
    assert s_local.llm_base_url == "http://127.0.0.1:11434/v1"

    # 3. Uzak uç noktası (OpenAI/NVIDIA) API key env olmadan hata vermeli
    with pytest.raises(ValueError, match="PD_LLM_API_KEY_ENV"):
        Settings(
            env="test",
            llm_provider="openai_compat",
            llm_base_url="https://api.openai.com/v1",
            llm_api_key_env="",
        )

    # 4. Uzak uç noktası API key env ile geçerli olmalı
    s_remote = Settings(
        env="test",
        llm_provider="openai_compat",
        llm_base_url="https://api.openai.com/v1",
        llm_api_key_env="OPENAI_API_KEY",
    )
    assert s_remote.llm_api_key_env == "OPENAI_API_KEY"


def test_missing_key_names_the_configured_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hata mesajı ANTHROPIC_API_KEY değil, yapılandırılan değişkeni söylemeli."""
    monkeypatch.delenv("TEST_LLM_KEY", raising=False)
    backend, _ = _backend(_ok())
    with pytest.raises(LLMNotConfigured, match="TEST_LLM_KEY"):
        _call(backend)


# ------------------------------------------------------------- istek
def test_request_uses_temperature_not_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec §11.5'in özgün sıcaklık kuralı bu arka uçta geri gelir.

    Claude sınıfı `temperature`'ı 400 ile reddettiği için yapılan sapma
    (İtiraz-3) sağlayıcıya özgüydü; burada geçerli değildir.
    """
    monkeypatch.setenv("TEST_LLM_KEY", "anahtar")
    backend, sent = _backend(_ok())

    _call(backend, effort="low")
    _call(backend, effort="high")

    assert "effort" not in sent[0]
    assert sent[0]["temperature"] == 0.0, "çıkarım deterministik olmalı"
    assert sent[1]["temperature"] == 0.7, "üretim yaratıcı olmalı"


def test_json_schema_is_sent_as_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_LLM_KEY", "anahtar")
    backend, sent = _backend(_ok())
    _call(backend)

    fmt = sent[0]["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["schema"] == SCHEMA
    assert fmt["json_schema"]["strict"] is True
    assert [m["role"] for m in sent[0]["messages"]] == ["system", "user"]


def test_bearer_key_is_read_from_the_configured_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_LLM_KEY", "gizli-anahtar")
    seen: list[str] = []

    def _handler(request: httpx.Request, _n: int) -> httpx.Response:
        seen.append(request.headers["Authorization"])
        assert str(request.url) == "https://sahte.ornek/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                "usage": {},
            },
        )

    backend, _ = _backend(_handler)
    _call(backend)
    assert seen == ["Bearer gizli-anahtar"]


# --------------------------------------------------------- düşüş merdiveni
def test_unsupported_json_mode_downgrades_and_is_remembered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sunucu `response_format` desteklemiyorsa çağrı ölmesin — ama sessiz kalmasın.

    Merdiven: json_schema -> guided_json -> json_object. Çalışan mod
    hatırlanır; aksi hâlde her çağrı boşa iki istek yapar.
    """
    monkeypatch.setenv("TEST_LLM_KEY", "anahtar")

    def _handler(request: httpx.Request, n: int) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("response_format", {}).get("type") == "json_schema":
            return httpx.Response(400, text="response_format json_schema not supported")
        if "nvext" in body:
            return httpx.Response(400, text="nvext not supported")
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"claims": []}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    backend, sent = _backend(_handler)

    text, _ = _call(backend)
    assert text == '{"claims": []}'
    assert len(sent) == 3, "merdivenin üç basamağı da denenmeli"
    assert sent[2]["response_format"] == {"type": "json_object"}
    # Şema zorlanamıyorsa prompta yazılır — yoksa model serbest JSON üretir.
    assert "claims" in sent[2]["messages"][0]["content"]

    _call(backend)
    assert len(sent) == 4, "çalışan mod hatırlanmadı; merdiven yeniden tırmanıldı"


def test_error_on_the_last_rung_is_raised_with_the_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """400'ün sebebi gövdede yazar; onu yutmak hata ayıklamayı imkânsız kılar."""
    monkeypatch.setenv("TEST_LLM_KEY", "anahtar")
    backend, _ = _backend(lambda _r, _n: httpx.Response(400, text="gecersiz istek"))

    with pytest.raises(LLMHTTPError, match="gecersiz istek"):
        _call(backend)


def test_model_not_available_404_does_not_climb_the_ladder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canlı koşumda görüldü: katalogda listelenen model hesaba açık olmayabilir.

    `404 Not found for account` bir lehçe sorunu değildir; merdiveni
    tırmanmak yalnızca iki çağrı israf eder.
    """
    monkeypatch.setenv("TEST_LLM_KEY", "anahtar")
    backend, sent = _backend(
        lambda _r, _n: httpx.Response(404, text='{"detail":"Not found for account"}')
    )

    with pytest.raises(LLMHTTPError) as exc:
        _call(backend)
    assert exc.value.status_code == 404
    assert len(sent) == 1, "404'te merdiven tırmanılmamalı"


def test_server_error_is_not_downgraded(monkeypatch: pytest.MonkeyPatch) -> None:
    """503 bir lehçe sorunu değildir; merdiven tırmanmak onu düzeltmez."""
    monkeypatch.setenv("TEST_LLM_KEY", "anahtar")
    backend, sent = _backend(
        lambda _r, _n: httpx.Response(503, text="asiri yuk"),
        _settings(llm_max_retries=1),
    )

    with pytest.raises(LLMHTTPError) as exc:
        _call(backend)
    assert exc.value.status_code == 503
    assert len(sent) == 1, "aynı lehçeyle bir kez denendi; merdiven tırmanılmadı"


# ------------------------------------------------------ geçici hata / yeniden deneme
def test_transient_503_is_retried_and_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ücretsiz katmanda canlı koşumda görülen hata:

    `503 ResourceExhausted: Worker local total request limit reached (16/16)`
    Geçicidir; yeniden denemeyen boru hattı bunu makale kaybı olarak yazar.
    """
    monkeypatch.setenv("TEST_LLM_KEY", "anahtar")
    monkeypatch.setattr("politikdesk.llm.client.time.sleep", lambda _s: None)

    def _handler(_request: httpx.Request, n: int) -> httpx.Response:
        if n < 2:
            return httpx.Response(503, text="ResourceExhausted: Worker local limit")
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"claims": []}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    backend, sent = _backend(_handler)
    text, _ = _call(backend)

    assert text == '{"claims": []}'
    assert len(sent) == 3, "iki geçici hatadan sonra üçüncü deneme başarılı olmalı"


def test_retry_honours_retry_after_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sunucu ne kadar bekleneceğini söylüyorsa tahmin etmeyelim."""
    monkeypatch.setenv("TEST_LLM_KEY", "anahtar")
    slept: list[float] = []
    monkeypatch.setattr("politikdesk.llm.client.time.sleep", slept.append)

    def _handler(_request: httpx.Request, n: int) -> httpx.Response:
        if n == 0:
            return httpx.Response(429, text="yavas", headers={"retry-after": "7"})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                "usage": {},
            },
        )

    backend, _ = _backend(_handler)
    _call(backend)
    assert slept == [7.0]


# -------------------------------------------------------------- yanıt
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('<think>Once dusuneyim...</think>{"claims": []}', '{"claims": []}'),
        ('```json\n{"claims": []}\n```', '{"claims": []}'),
        ('Bir sey dusundum</think>{"claims": []}', '{"claims": []}'),
        ('  {"claims": []}  ', '{"claims": []}'),
    ],
)
def test_reasoning_and_fences_are_stripped_before_json(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: str
) -> None:
    """Açık modeller JSON'un önüne düşünce bloğu / kod bloğu koyar.

    Bu sağlayıcıya özgü bir kabuktur; `LLMClient` sağlayıcı-agnostik
    kalsın diye arka uçta soyulur.
    """
    monkeypatch.setenv("TEST_LLM_KEY", "anahtar")
    backend, _ = _backend(_ok(raw))
    text, _ = _call(backend)
    assert text == expected
    assert json.loads(text) == {"claims": []}


def test_cached_tokens_are_not_counted_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    """`prompt_tokens` önbellekten okunanı da içerir; muhasebe ayrıştırmalı."""
    monkeypatch.setenv("TEST_LLM_KEY", "anahtar")
    backend, _ = _backend(
        _ok(
            usage={
                "prompt_tokens": 1000,
                "completion_tokens": 200,
                "prompt_tokens_details": {"cached_tokens": 400},
            }
        )
    )
    _, usage = _call(backend)

    assert usage["input_tokens"] == 600
    assert usage["cache_read_tokens"] == 400
    assert usage["output_tokens"] == 200


def test_content_filter_is_a_refusal_not_a_parse_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_LLM_KEY", "anahtar")
    backend, _ = _backend(
        lambda _r, _n: httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}],
                "usage": {},
            },
        )
    )
    with pytest.raises(LLMRefusal):
        _call(backend)


def test_empty_content_is_reported_with_the_finish_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Boş çıktı `json.loads`'ta anlamsız hata vermesin."""
    monkeypatch.setenv("TEST_LLM_KEY", "anahtar")
    backend, _ = _backend(
        lambda _r, _n: httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
                "usage": {},
            },
        )
    )
    with pytest.raises(SchemaValidationError, match="length"):
        _call(backend)


# ------------------------------------------------------- uçtan uca muhasebe
def test_free_tier_costs_zero_but_tokens_are_still_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ücretsiz katmanda maliyet 0'dır; token muhasebesi yine tutulur.

    Kota takibi ve sağlayıcı karşılaştırması maliyete değil token'a bakar.
    """
    monkeypatch.setenv("TEST_LLM_KEY", "anahtar")
    settings = _settings()
    backend, _ = _backend(_ok(), settings)
    ledger = InMemoryLedger()
    client = LLMClient(
        backend=backend,
        guard=BudgetGuard(ledger=ledger, settings=settings),
        settings=settings,
    )

    result = client.complete_json(purpose="claim_extraction", system="s", user="u", schema=SCHEMA)

    assert result.data == {"claims": []}
    assert result.model == MODEL
    assert result.cost_usd == 0.0
    assert ledger.calls[0].input_tokens == 1000
    assert ledger.calls[0].output_tokens == 200


def test_local_endpoint_works_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Yerel uç nokta (Ollama/localhost) API anahtarı olmadan çalışabilir."""
    monkeypatch.delenv("TEST_LLM_KEY", raising=False)
    settings = _settings(llm_base_url="http://127.0.0.1:11434/v1", llm_api_key_env="")
    backend, sent = _backend(_ok(), settings)
    text, usage = backend.complete_json(
        model="llama3.2",
        system="s",
        user="u",
        schema=SCHEMA,
        effort="low",
        max_tokens=1000,
    )
    assert json.loads(text) == {"claims": []}
    assert usage["input_tokens"] == 1000
    assert sent[0]["model"] == "llama3.2"


