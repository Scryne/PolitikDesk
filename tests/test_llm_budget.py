"""F0-17 — LLM adaptörü ve bütçe sayacı testleri.

DoD: "Çağrı token'ları loglanıyor; günlük tavan aşılınca BudgetExceeded
fırlatıyor."
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from politikdesk.config import Settings
from politikdesk.llm.budget import BudgetGuard, CallRecord, InMemoryLedger
from politikdesk.llm.client import LLMClient
from politikdesk.llm.errors import BudgetExceeded, LLMRefusal, SchemaValidationError
from politikdesk.llm.pricing import PRICES, UnknownModelError, estimate_cost_usd


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "env": "test",
        "llm_daily_budget_usd": 1.0,
        "llm_monthly_budget_usd": 10.0,
        "llm_model_extraction": "claude-sonnet-5",
        "llm_model_generation": "claude-opus-5",
    }
    base.update(overrides)
    return Settings(**base)


# ---------------------------------------------------------------- fiyatlama
def test_pricing_table_covers_configured_models() -> None:
    s = _settings()
    assert s.llm_model_extraction in PRICES
    assert s.llm_model_generation in PRICES


def test_cost_is_computed_per_million_tokens() -> None:
    # claude-opus-5: 5 $/M girdi, 25 $/M çıktı
    cost = estimate_cost_usd("claude-opus-5", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == pytest.approx(30.0)


def test_cache_reads_are_cheaper_than_fresh_input() -> None:
    fresh = estimate_cost_usd("claude-opus-5", input_tokens=100_000)
    cached = estimate_cost_usd("claude-opus-5", cache_read_tokens=100_000)
    assert cached == pytest.approx(fresh * 0.10)


def test_sonnet_intro_pricing_expires() -> None:
    """Tanıtım fiyatı maliyet modelini yanıltmasın: tarihe bağlı hesaplanır."""
    during = estimate_cost_usd("claude-sonnet-5", input_tokens=1_000_000, on=date(2026, 8, 15))
    after = estimate_cost_usd("claude-sonnet-5", input_tokens=1_000_000, on=date(2026, 9, 1))
    assert during == pytest.approx(2.0)
    assert after == pytest.approx(3.0)


def test_unknown_model_raises_instead_of_silently_costing_zero() -> None:
    with pytest.raises(UnknownModelError):
        estimate_cost_usd("gpt-hayali-9", input_tokens=1000)


def test_local_models_return_zero_cost() -> None:
    """Yerel Ollama/vLLM modelleri $0.0 maliyetle FREE_TIER döner."""
    assert estimate_cost_usd("llama3.2", input_tokens=100_000, output_tokens=50_000) == 0.0
    assert estimate_cost_usd("ollama/qwen2.5:72b", input_tokens=500_000) == 0.0
    assert estimate_cost_usd("local/deepseek-r1", input_tokens=200_000) == 0.0


# ------------------------------------------------------------------- bütçe
def test_guard_allows_calls_below_cap() -> None:
    guard = BudgetGuard(ledger=InMemoryLedger(), settings=_settings())
    guard.check()  # hata fırlatmamalı


def test_daily_cap_raises_budget_exceeded() -> None:
    ledger = InMemoryLedger()
    guard = BudgetGuard(ledger=ledger, settings=_settings(llm_daily_budget_usd=1.0))

    ledger.record(CallRecord(purpose="claims", model="claude-sonnet-5", cost_usd=0.99))
    guard.check()  # hâlâ tavan altında

    ledger.record(CallRecord(purpose="claims", model="claude-sonnet-5", cost_usd=0.02))
    with pytest.raises(BudgetExceeded) as exc:
        guard.check()
    assert exc.value.period == "Günlük"


def test_monthly_cap_raises_budget_exceeded() -> None:
    ledger = InMemoryLedger()
    guard = BudgetGuard(
        ledger=ledger,
        settings=_settings(llm_daily_budget_usd=1000.0, llm_monthly_budget_usd=5.0),
    )
    ledger.record(CallRecord(purpose="draft", model="claude-opus-5", cost_usd=6.0))
    with pytest.raises(BudgetExceeded) as exc:
        guard.check()
    assert exc.value.period == "Aylık"


def test_estimated_cost_is_included_in_the_check() -> None:
    """Bir çağrının tavanı *aşarak* tamamlanması değil, başlamadan durması hedeflenir."""
    ledger = InMemoryLedger()
    guard = BudgetGuard(ledger=ledger, settings=_settings(llm_daily_budget_usd=1.0))
    ledger.record(CallRecord(purpose="claims", model="claude-sonnet-5", cost_usd=0.90))

    guard.check(estimated_cost_usd=0.05)
    with pytest.raises(BudgetExceeded):
        guard.check(estimated_cost_usd=0.20)


def test_yesterdays_spend_does_not_count_against_today() -> None:
    ledger = InMemoryLedger()
    ledger.record(
        CallRecord(
            purpose="claims",
            model="claude-sonnet-5",
            cost_usd=99.0,
            created_at=datetime.now(UTC) - timedelta(days=2),
        )
    )
    guard = BudgetGuard(ledger=ledger, settings=_settings())
    assert guard.ledger.spent_today_usd() == 0.0


# ------------------------------------------------------------------ istemci
class _FakeBackend:
    """Sahte arka uç — API anahtarı ve ağ gerektirmez."""

    def __init__(self, text: str = '{"claims": []}', usage: dict[str, int] | None = None):
        self.text = text
        self.usage = usage or {
            "input_tokens": 1000,
            "output_tokens": 200,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        }
        self.calls: list[dict[str, Any]] = []

    def complete_json(self, **kwargs: Any) -> tuple[str, dict[str, int]]:
        self.calls.append(kwargs)
        return self.text, self.usage


def _client(backend: Any, settings: Settings | None = None) -> tuple[LLMClient, InMemoryLedger]:
    s = settings or _settings()
    ledger = InMemoryLedger()
    return (
        LLMClient(backend=backend, guard=BudgetGuard(ledger=ledger, settings=s), settings=s),
        ledger,
    )


SCHEMA = {"type": "object", "properties": {"claims": {"type": "array"}}}


def test_successful_call_is_recorded_with_tokens_and_cost() -> None:
    client, ledger = _client(_FakeBackend())
    result = client.complete_json(
        purpose="claims",
        system="sys",
        user="usr",
        schema=SCHEMA,
        prompt_version="claims.v1",
    )

    assert result.data == {"claims": []}
    assert len(ledger.calls) == 1
    rec = ledger.calls[0]
    assert rec.input_tokens == 1000
    assert rec.output_tokens == 200
    assert rec.cost_usd > 0
    assert rec.prompt_version == "claims.v1"
    assert rec.succeeded is True


def test_extraction_and_generation_use_different_models_and_effort() -> None:
    """Spec §11.5: ucuz model ile çıkarım, pahalı model ile üretim."""
    backend = _FakeBackend()
    client, _ = _client(backend)

    client.complete_json(purpose="claims", system="s", user="u", schema=SCHEMA, task="extraction")
    client.complete_json(purpose="draft", system="s", user="u", schema=SCHEMA, task="generation")

    assert backend.calls[0]["model"] == "claude-sonnet-5"
    assert backend.calls[1]["model"] == "claude-opus-5"
    assert backend.calls[0]["effort"] == "low"
    assert backend.calls[1]["effort"] == "high"


def test_no_sampling_parameters_are_sent() -> None:
    """Seçilen model sınıfı temperature/top_p/top_k'yı 400 ile reddeder."""
    backend = _FakeBackend()
    client, _ = _client(backend)
    client.complete_json(purpose="claims", system="s", user="u", schema=SCHEMA)

    sent = backend.calls[0]
    for banned in ("temperature", "top_p", "top_k"):
        assert banned not in sent


def test_budget_exceeded_prevents_the_call_entirely() -> None:
    backend = _FakeBackend()
    s = _settings(llm_daily_budget_usd=0.001)
    ledger = InMemoryLedger()
    ledger.record(CallRecord(purpose="x", model="claude-opus-5", cost_usd=0.002))
    client = LLMClient(backend=backend, guard=BudgetGuard(ledger=ledger, settings=s), settings=s)

    with pytest.raises(BudgetExceeded):
        client.complete_json(purpose="draft", system="s", user="u", schema=SCHEMA)

    assert backend.calls == [], "Bütçe aşılmışken arka uca çağrı gitmemeli"


def test_failed_call_is_still_recorded() -> None:
    class _Boom:
        def complete_json(self, **_: Any) -> tuple[str, dict[str, int]]:
            raise LLMRefusal(category="cyber", explanation="test")

    client, ledger = _client(_Boom())
    with pytest.raises(LLMRefusal):
        client.complete_json(purpose="draft", system="s", user="u", schema=SCHEMA)

    assert len(ledger.calls) == 1
    assert ledger.calls[0].succeeded is False
    assert ledger.calls[0].error_type == "LLMRefusal"


def test_invalid_json_output_raises_schema_error() -> None:
    client, _ = _client(_FakeBackend(text="bu JSON değil"))
    with pytest.raises(SchemaValidationError):
        client.complete_json(purpose="claims", system="s", user="u", schema=SCHEMA)


def test_grounding_instruction_is_available_to_prompts() -> None:
    """Spec §11.5: grounding kuralı promptta yer almalı."""
    from politikdesk.llm.client import GROUNDING_INSTRUCTION

    assert "Kanıtta olmayan" in GROUNDING_INSTRUCTION


# ---------------------------------------------------- yapılandırma eksikliği
def test_missing_api_key_raises_named_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Anahtar yokken SDK'nın ham `TypeError`'ı yerine anlaşılır hata.

    Denetimde görülen davranış: `make claims` her olay için ayrı ayrı
    "TypeError: Could not resolve authentication method" logluyordu — tek bir
    yapılandırma eksikliği 5 satır anlamsız hata gibi görünüyordu.
    """
    from politikdesk.llm.client import _AnthropicBackend
    from politikdesk.llm.errors import LLMNotConfigured

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    backend = _AnthropicBackend(Settings())

    with pytest.raises(LLMNotConfigured, match="ANTHROPIC_API_KEY"):
        _ = backend.client


def test_missing_api_key_is_not_written_to_the_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hiç yapılmamış çağrı `llm_calls` muhasebesini kirletmemeli."""
    from politikdesk.llm.errors import LLMNotConfigured

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    class _UnconfiguredBackend:
        def complete_json(self, **_: Any) -> tuple[str, Any]:
            raise LLMNotConfigured("ANTHROPIC_API_KEY")

    client, ledger = _client(_UnconfiguredBackend())

    with pytest.raises(LLMNotConfigured):
        client.complete_json(purpose="claims", system="s", user="u", schema=SCHEMA)

    assert ledger.calls == [], "Yapılmamış çağrı defterine yazılmış"
