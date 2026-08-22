"""Test suite for Corroboration Evaluation Harness.

Verifies that the corroboration and independence rules preserve strict
epistemic invariants across the golden benchmark corpus.
"""

from __future__ import annotations

import pytest

from eval.corroboration_eval_harness import CORPUS, run_corroboration_evaluation


def test_corroboration_eval_harness_full_pass() -> None:
    """Altın korpus üzerinde corroboration harness %100 precision ile geçmelidir."""
    metrics = run_corroboration_evaluation()
    assert metrics.failed_cases == 0, f"Değerlendirme başarısız: {metrics.failures}"
    assert metrics.passed_cases == metrics.total_cases
    assert metrics.precision == 1.0
    assert metrics.false_corroboration_rate == 0.0


@pytest.mark.parametrize("test_case", CORPUS, ids=lambda tc: tc.id)
def test_each_corroboration_case(test_case) -> None:  # noqa: ANN001
    """Her vaka tekil olarak test edilir."""
    metrics = run_corroboration_evaluation([test_case])
    assert metrics.failed_cases == 0, f"Vaka başarısız oldu: {test_case.id} -> {metrics.failures}"
