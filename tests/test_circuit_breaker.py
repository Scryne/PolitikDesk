"""Devre Kesici (Circuit Breaker) mekanizması birim testleri (F5 / B-98)."""

from __future__ import annotations

import time

import pytest

from politikdesk.ingestion.circuit import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    SourceCircuitRegistry,
    get_circuit,
)


def test_circuit_breaker_starts_closed() -> None:
    cb = CircuitBreaker(host="api.tcmb.gov.tr", failure_threshold=3, recovery_timeout=2.0)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True
    metrics = cb.get_metrics()
    assert metrics["is_healthy"] is True
    assert metrics["state"] == "closed"


def test_circuit_breaker_trips_to_open_after_threshold() -> None:
    cb = CircuitBreaker(host="api.tuik.gov.tr", failure_threshold=3, recovery_timeout=1.0)

    cb.record_failure("HTTP 500")
    assert cb.state == CircuitState.CLOSED

    cb.record_failure("HTTP 502")
    assert cb.state == CircuitState.CLOSED

    cb.record_failure("HTTP 503")
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False

    with pytest.raises(CircuitOpenError) as exc_info:
        cb.check_or_raise()

    assert "api.tuik.gov.tr" in str(exc_info.value)
    assert exc_info.value.retry_after_seconds > 0


def test_circuit_breaker_recovers_via_half_open() -> None:
    cb = CircuitBreaker(host="rsshub.local", failure_threshold=2, recovery_timeout=0.1)

    cb.record_failure("ConnectTimeout")
    cb.record_failure("ConnectTimeout")
    assert cb.state == CircuitState.OPEN

    # Soğuma süresini bekle
    time.sleep(0.15)

    # İlk probe isteğine izin verilmeli
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN

    # Başarılı olunca devre tekrar CLOSED olmalı
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_circuit_breaker_half_open_failure_trips_immediately() -> None:
    cb = CircuitBreaker(host="resmigazete.gov.tr", failure_threshold=3, recovery_timeout=0.1)

    cb.record_failure("500")
    cb.record_failure("500")
    cb.record_failure("500")
    assert cb.state == CircuitState.OPEN

    time.sleep(0.15)
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN

    # Yarım-açık probe başarısız olursa tek seferde tekrar OPEN olmalı
    cb.record_failure("503")
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False


def test_source_circuit_registry() -> None:
    reg = SourceCircuitRegistry()
    c1 = reg.get("api.example.com")
    c2 = reg.get("API.EXAMPLE.COM")
    assert c1 is c2

    c1.record_failure("Error")
    metrics = reg.all_metrics()
    assert len(metrics) == 1
    assert metrics[0]["host"] == "api.example.com"
    assert metrics[0]["failure_count"] == 1

    reg.reset_all()
    assert c1.state == CircuitState.CLOSED
    assert c1.get_metrics()["failure_count"] == 0


def test_global_get_circuit_helper() -> None:
    c = get_circuit("global.example.com")
    assert c.host == "global.example.com"
    assert c.state == CircuitState.CLOSED

