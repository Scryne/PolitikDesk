"""Faz 24: Source Quality Score (SQS) Modeli Testleri."""

from __future__ import annotations

from politikdesk.ingestion.quality import SourceMetrics, calculate_sqs, latency_to_score


def test_latency_scoring_tiers() -> None:
    assert latency_to_score(150.0) == 100.0
    assert latency_to_score(350.0) == 90.0
    assert latency_to_score(750.0) == 70.0
    assert latency_to_score(2000.0) == 45.0
    assert latency_to_score(8000.0) == 0.0


def test_official_tier1_source_sqs() -> None:
    """TCMB / Resmi Gazete gibi Tier 1 resmi kaynaklar yüksek SQS (90+) almalı."""
    tcmb_metrics = SourceMetrics(
        authority=100.0,
        reliability=100.0,
        freshness=90.0,
        latency_ms=180.0,  # L: 100
        coverage=95.0,
        marginal_value=95.0,
        uptime_ratio=0.999,  # V: 99.9
    )
    score = calculate_sqs(tcmb_metrics)
    assert score >= 95.0, f"Tier 1 kaynak skoru yetersiz: {score}"


def test_wire_agency_source_sqs() -> None:
    """Anadolu Ajansı / Reuters gibi haber ajansları yüksek güncellik ve güvenilirlik ile 85+ almalı."""
    wire_metrics = SourceMetrics(
        authority=85.0,
        reliability=90.0,
        freshness=100.0,
        latency_ms=300.0,
        coverage=85.0,
        marginal_value=70.0,
        uptime_ratio=0.995,
    )
    score = calculate_sqs(wire_metrics)
    assert 80.0 <= score <= 92.0, f"Ajans skoru beklenmedik: {score}"


def test_slow_unreliable_source_sqs() -> None:
    """Düşük güvenilirlikli ve yavaş kaynak düşük SQS (<60) almalı."""
    low_metrics = SourceMetrics(
        authority=40.0,
        reliability=50.0,
        freshness=60.0,
        latency_ms=4500.0,
        coverage=40.0,
        marginal_value=30.0,
        uptime_ratio=0.85,
    )
    score = calculate_sqs(low_metrics)
    assert score < 50.0, f"Düşük kaliteli kaynak fazla puan aldı: {score}"
