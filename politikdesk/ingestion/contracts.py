"""Kaynak Güvenilirlik Sözleşmesi ve Arıza Sınıflandırma Katmanı (Source Reliability Contracts).

Her Tier-1 ve harici kaynak için beklenen protokol, zaman aşımı, devre kesici,
hata sınıflandırma ve operatör teşhis sözleşmesini tek noktadan tanımlar.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class FailureCategory(StrEnum):
    """Harici kaynak arıza sınıfları."""

    SSL_HANDSHAKE_RESET = "ssl_handshake_reset"
    CONNECT_TIMEOUT = "connect_timeout"
    READ_TIMEOUT = "read_timeout"
    DNS_FAILURE = "dns_failure"
    WAF_CHALLENGE = "waf_challenge"
    HTTP_STATUS_ERROR = "http_status_error"
    CIRCUIT_OPEN = "circuit_open"
    UNKNOWN = "unknown"


def classify_failure(
    exc: Exception | None = None,
    status_code: int | None = None,
    response_text: str | None = None,
) -> FailureCategory:
    """İstisna veya yanıt gövdesini deterministik olarak sınıflandırır."""
    if exc is not None:
        exc_type = type(exc).__name__
        exc_msg = str(exc).lower()

        if "circuitopen" in exc_type.lower():
            return FailureCategory.CIRCUIT_OPEN

        if (
            "ssleof" in exc_type.lower()
            or "unexpected_eof_while_reading" in exc_msg
            or "10054" in exc_msg
            or "connection reset" in exc_msg
        ):
            return FailureCategory.SSL_HANDSHAKE_RESET

        if "connecttimeout" in exc_type.lower() or "connection timed out" in exc_msg:
            return FailureCategory.CONNECT_TIMEOUT

        if "readtimeout" in exc_type.lower() or "read timed out" in exc_msg:
            return FailureCategory.READ_TIMEOUT

        if (
            "gaierror" in exc_type.lower()
            or "nameresolutionerror" in exc_type.lower()
            or "getaddrinfo" in exc_msg
        ):
            return FailureCategory.DNS_FAILURE

    if response_text and any(
        marker in response_text.lower()
        for marker in ("document.cookie=", "challenge-form", "cf-ray", "bot verification")
    ):
        return FailureCategory.WAF_CHALLENGE

    if status_code and status_code >= 400:
        return FailureCategory.HTTP_STATUS_ERROR

    return FailureCategory.UNKNOWN


@dataclass(frozen=True)
class SourceReliabilityContract:
    """Tek bir kaynağın güvenilirlik ve işletim sözleşmesi."""

    source_slug: str
    tier: int
    expected_protocol: str  # https, sdmx, rss, api
    expected_frequency: str  # continuous, hourly, daily, monthly
    timeout_seconds: float
    connect_timeout: float
    read_timeout: float
    max_retries: int
    circuit_threshold: int
    circuit_cooldown: float
    fallback_behavior: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_slug": self.source_slug,
            "tier": self.tier,
            "expected_protocol": self.expected_protocol,
            "expected_frequency": self.expected_frequency,
            "timeout_seconds": self.timeout_seconds,
            "connect_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
            "max_retries": self.max_retries,
            "circuit_threshold": self.circuit_threshold,
            "circuit_cooldown": self.circuit_cooldown,
            "fallback_behavior": self.fallback_behavior,
        }


# Tier-1 Resmi Kurum Güvenilirlik Sözleşmeleri
TIER1_CONTRACTS: dict[str, SourceReliabilityContract] = {
    "resmi-gazete": SourceReliabilityContract(
        source_slug="resmi-gazete",
        tier=1,
        expected_protocol="https",
        expected_frequency="daily",
        timeout_seconds=25.0,
        connect_timeout=8.0,
        read_timeout=18.0,
        max_retries=3,
        circuit_threshold=4,
        circuit_cooldown=120.0,
        fallback_behavior="record_failure_and_skip",
    ),
    "cb-kararname": SourceReliabilityContract(
        source_slug="cb-kararname",
        tier=1,
        expected_protocol="https",
        expected_frequency="daily",
        timeout_seconds=15.0,
        connect_timeout=5.0,
        read_timeout=10.0,
        max_retries=2,
        circuit_threshold=3,
        circuit_cooldown=90.0,
        fallback_behavior="record_failure_and_skip",
    ),
    "sayistay": SourceReliabilityContract(
        source_slug="sayistay",
        tier=1,
        expected_protocol="https",
        expected_frequency="daily",
        timeout_seconds=20.0,
        connect_timeout=5.0,
        read_timeout=15.0,
        max_retries=2,
        circuit_threshold=3,
        circuit_cooldown=90.0,
        fallback_behavior="record_failure_and_skip",
    ),
    "tuik": SourceReliabilityContract(
        source_slug="tuik",
        tier=1,
        expected_protocol="sdmx",
        expected_frequency="monthly",
        timeout_seconds=30.0,
        connect_timeout=10.0,
        read_timeout=20.0,
        max_retries=3,
        circuit_threshold=3,
        circuit_cooldown=180.0,
        fallback_behavior="record_failure_and_skip",
    ),
    "tcmb": SourceReliabilityContract(
        source_slug="tcmb",
        tier=1,
        expected_protocol="https",
        expected_frequency="daily",
        timeout_seconds=20.0,
        connect_timeout=6.0,
        read_timeout=14.0,
        max_retries=3,
        circuit_threshold=3,
        circuit_cooldown=60.0,
        fallback_behavior="record_failure_and_skip",
    ),
    "sbb": SourceReliabilityContract(
        source_slug="sbb",
        tier=1,
        expected_protocol="https",
        expected_frequency="monthly",
        timeout_seconds=20.0,
        connect_timeout=5.0,
        read_timeout=15.0,
        max_retries=2,
        circuit_threshold=3,
        circuit_cooldown=90.0,
        fallback_behavior="record_failure_and_skip",
    ),
    "tbmm-tutanak": SourceReliabilityContract(
        source_slug="tbmm-tutanak",
        tier=1,
        expected_protocol="https",
        expected_frequency="daily",
        timeout_seconds=25.0,
        connect_timeout=8.0,
        read_timeout=17.0,
        max_retries=3,
        circuit_threshold=3,
        circuit_cooldown=120.0,
        fallback_behavior="record_failure_and_skip",
    ),
    "hazine": SourceReliabilityContract(
        source_slug="hazine",
        tier=1,
        expected_protocol="https",
        expected_frequency="monthly",
        timeout_seconds=20.0,
        connect_timeout=5.0,
        read_timeout=15.0,
        max_retries=2,
        circuit_threshold=3,
        circuit_cooldown=90.0,
        fallback_behavior="record_failure_and_skip",
    ),
}


def get_source_contract(source_slug: str, tier: int = 3) -> SourceReliabilityContract:
    """Kaynak slug'ına göre sözleşmeyi döner veya katmanına göre varsayılan üretir."""
    normalized = source_slug.lower().strip()
    if normalized in TIER1_CONTRACTS:
        return TIER1_CONTRACTS[normalized]

    # Standart medya / ajans varsayılan sözleşmesi
    return SourceReliabilityContract(
        source_slug=normalized,
        tier=tier,
        expected_protocol="rss",
        expected_frequency="hourly",
        timeout_seconds=20.0,
        connect_timeout=5.0,
        read_timeout=15.0,
        max_retries=2,
        circuit_threshold=3,
        circuit_cooldown=60.0,
        fallback_behavior="record_failure_and_skip",
    )
