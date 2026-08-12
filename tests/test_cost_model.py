"""Maliyet modeli testleri (F0-06, F0-07, G0 koşul 8)."""

from __future__ import annotations

import pytest

from scripts.cost_model import COST_TARGET_PER_USER_USD, Assumptions, compute


def test_fixed_costs_are_shared_variable_costs_are_not() -> None:
    """Modelin çekirdek ayrımı: ingestion paylaşılır, üretim paylaşılmaz."""
    b = compute(Assumptions())
    assert b.per_user(10) > b.per_user(100) > b.per_user(1000)
    # Kullanıcı sonsuza giderse maliyet değişken kısma yakınsar.
    assert b.per_user(1_000_000) == pytest.approx(b.variable_per_user, abs=0.01)


def test_break_even_user_count_is_reported_honestly() -> None:
    """Hedefe hangi ölçekten sonra ulaşıldığı belirsiz kalmamalı."""
    b = compute(Assumptions())
    break_even = b.fixed_total / (COST_TARGET_PER_USER_USD - b.variable_per_user)
    assert break_even > 0, "Değişken maliyet tek başına hedefi aşıyor"
    assert b.per_user(int(break_even) + 1) <= COST_TARGET_PER_USER_USD


def test_variable_cost_alone_stays_under_target() -> None:
    """Değişken maliyet tek başına 8 $'ı aşarsa model hiçbir ölçekte tutmaz."""
    b = compute(Assumptions())
    assert b.variable_per_user < COST_TARGET_PER_USER_USD


def test_generation_dominates_variable_cost() -> None:
    """Pahalı model taslak üretiminde; brifing ucuz modelde olmalı."""
    b = compute(Assumptions())
    assert b.variable_drafts > b.variable_briefings


def test_dedup_reduces_extraction_cost() -> None:
    """F1-10/F1-11 tekilleştirme doğrudan maliyet azaltımıdır."""
    without = compute(Assumptions(dedup_rate=0.0))
    with_dedup = compute(Assumptions(dedup_rate=0.25))
    assert with_dedup.fixed_extraction < without.fixed_extraction


def test_cache_hit_ratio_reduces_extraction_cost() -> None:
    """Spec §11.5: statik sistem promptu önbelleklenir."""
    cold = compute(Assumptions(cache_hit_ratio=0.0))
    warm = compute(Assumptions(cache_hit_ratio=0.85))
    assert warm.fixed_extraction < cold.fixed_extraction


def test_x_api_costs_nothing_in_mvp() -> None:
    """Spec §9.4 / D7: MVP'de X API kullanılmaz."""
    assert all(cost == 0.0 for _, cost in Assumptions().x_api_scenarios)
