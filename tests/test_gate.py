"""Gate Runner Fail-Closed ve Zero-Data / Adversarial Testleri (G4.4).

Hiçbir koşulda 0/0 veya boş verinin yapay PASS üretmediğini;
PENDING_OBSERVATION ve INSUFFICIENT_DATA durumlarının fail-closed
şekilde korunduğunu test eder.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from scripts.phase5_gate import (
    GateStatus,
    check_briefing_delivery,
    check_collection_failures,
    check_continuity,
    check_correction_rate,
    check_diversity_ratio,
    check_grounding_rate,
)


def test_continuity_fails_on_empty_table() -> None:
    cur = MagicMock()
    cur.fetchone.return_value = {"min_ts": None, "max_ts": None, "count": 0}
    res = check_continuity(cur)
    assert res.status == GateStatus.FAIL
    assert not res.passed


def test_continuity_is_pending_observation_when_under_7_days() -> None:
    cur = MagicMock()
    t0 = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
    t1 = t0 + timedelta(days=2, hours=12)  # 2.5 gün
    cur.fetchone.return_value = {"min_ts": t0, "max_ts": t1, "count": 50}
    res = check_continuity(cur)
    assert res.status == GateStatus.PENDING_OBSERVATION
    assert not res.passed
    assert "2.5 gün" in res.measured


def test_continuity_passes_when_7_or_more_days() -> None:
    cur = MagicMock()
    t0 = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    t1 = t0 + timedelta(days=7, hours=2)  # 7.1 gün
    cur.fetchone.return_value = {"min_ts": t0, "max_ts": t1, "count": 200}
    res = check_continuity(cur)
    assert res.status == GateStatus.PASS
    assert res.passed


def test_collection_failures_insufficient_data_when_under_100_fetches() -> None:
    cur = MagicMock()
    cur.fetchone.return_value = {"total": 45, "failed": 0}
    res = check_collection_failures(cur, hours=24)
    assert res.status == GateStatus.INSUFFICIENT_DATA
    assert not res.passed


def test_collection_failures_passes_on_low_failure_rate() -> None:
    cur = MagicMock()
    cur.fetchone.return_value = {"total": 200, "failed": 2}  # %1.0
    res = check_collection_failures(cur, hours=24)
    assert res.status == GateStatus.PASS
    assert res.passed
    assert res.measured == "%1.00"


def test_correction_rate_insufficient_data_when_sample_size_small() -> None:
    cur = MagicMock()
    # 7 açılan olay, 1 feedback
    cur.fetchone.return_value = {"opened_count": 7, "feedback_count": 1}
    res = check_correction_rate(cur)
    assert res.status == GateStatus.INSUFFICIENT_DATA
    assert not res.passed


def test_correction_rate_passes_when_sample_size_large_and_rate_low() -> None:
    cur = MagicMock()
    cur.fetchone.return_value = {"opened_count": 50, "feedback_count": 1}  # %2.0 <= %3.0
    res = check_correction_rate(cur)
    assert res.status == GateStatus.PASS
    assert res.passed
    assert res.measured == "%2.00"


def test_correction_rate_fails_when_sample_size_large_and_rate_high() -> None:
    cur = MagicMock()
    cur.fetchone.return_value = {"opened_count": 50, "feedback_count": 4}  # %8.0 > %3.0
    res = check_correction_rate(cur)
    assert res.status == GateStatus.FAIL
    assert not res.passed


def test_diversity_ratio_insufficient_data_when_under_10_events() -> None:
    cur = MagicMock()
    cur.fetchone.return_value = {"val": 3.0, "n": 6}
    res = check_diversity_ratio(cur)
    assert res.status == GateStatus.INSUFFICIENT_DATA
    assert not res.passed


def test_grounding_pending_observation_when_no_accepted_drafts() -> None:
    cur = MagicMock()
    cur.fetchone.return_value = {"total_drafts": 10, "accepted_drafts": 0, "ungrounded_drafts": 0}
    res = check_grounding_rate(cur)
    assert res.status == GateStatus.PENDING_OBSERVATION
    assert not res.passed


def test_grounding_passes_when_accepted_drafts_have_zero_ungrounded() -> None:
    cur = MagicMock()
    cur.fetchone.return_value = {"total_drafts": 10, "accepted_drafts": 8, "ungrounded_drafts": 0}
    res = check_grounding_rate(cur)
    assert res.status == GateStatus.PASS
    assert res.passed


def test_briefing_delivery_pending_observation_when_under_14_slots() -> None:
    cur = MagicMock()
    cur.fetchone.return_value = {"total": 4, "sent": 4, "errors": 0}
    res = check_briefing_delivery(cur)
    assert res.status == GateStatus.PENDING_OBSERVATION
    assert not res.passed


def test_continuity_with_since_parameter() -> None:
    cur = MagicMock()
    since = datetime(2026, 8, 15, 13, 0, tzinfo=UTC)
    t_max = datetime(2026, 8, 17, 13, 0, tzinfo=UTC)
    cur.fetchone.return_value = {"min_ts": since, "max_ts": t_max, "count": 40}
    res = check_continuity(cur, since=since)
    assert res.status == GateStatus.PENDING_OBSERVATION
    assert not res.passed
    assert "2.0 gün (40 makale)" in res.measured


def test_collection_failures_with_since_parameter() -> None:
    cur = MagicMock()
    since = datetime(2026, 8, 15, 13, 0, tzinfo=UTC)
    cur.fetchone.return_value = {"total": 150, "failed": 0}
    res = check_collection_failures(cur, since=since)
    assert res.status == GateStatus.PASS
    assert res.passed
    assert res.measured == "%0.00"
    assert "Sıfırlamadan" in res.evidence


def test_correction_rate_with_since_parameter() -> None:
    cur = MagicMock()
    since = datetime(2026, 8, 15, 13, 0, tzinfo=UTC)
    cur.fetchone.return_value = {"opened_count": 40, "feedback_count": 1}
    res = check_correction_rate(cur, since=since)
    assert res.status == GateStatus.PASS
    assert res.passed
    assert res.measured == "%2.50"


def test_grounding_rate_with_since_parameter() -> None:
    cur = MagicMock()
    since = datetime(2026, 8, 15, 13, 0, tzinfo=UTC)
    cur.fetchone.return_value = {"total_drafts": 20, "accepted_drafts": 15, "ungrounded_drafts": 0}
    res = check_grounding_rate(cur, since=since)
    assert res.status == GateStatus.PASS
    assert res.passed
    assert res.measured == "%0.0"


def test_briefing_delivery_with_since_parameter() -> None:
    cur = MagicMock()
    since = datetime(2026, 8, 15, 13, 0, tzinfo=UTC)
    cur.fetchone.return_value = {"total": 14, "sent": 14, "errors": 0}
    res = check_briefing_delivery(cur, since=since)
    assert res.status == GateStatus.PASS
    assert res.passed
    assert res.measured == "14/14 gönderildi"
