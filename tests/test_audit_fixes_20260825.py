"""Regression tests for Principal Engineering Audit fixes (2026-08-25)."""

from __future__ import annotations

from unittest.mock import patch

from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.clustering.assigner import CandidateOutcome, CandidateTrace
from politikdesk.config import Settings
from politikdesk.nlp.claims_pipeline import PENDING_EVENTS_SQL
from politikdesk.pipeline_health import STAGES


def test_claims_query_filters_active_publication_cycle() -> None:
    """SRE-001: pipeline_health claims query must filter by active publication cycle."""
    claims_stage = next(s for s in STAGES if s.key == "claims")
    assert "publication_cycles" in claims_stage.sql
    assert "status = 'active'" in claims_stage.sql
    assert "active_cycle" in claims_stage.sql


def test_pending_events_sql_filters_active_publication_cycle() -> None:
    """SRE-001: PENDING_EVENTS_SQL must filter by active publication cycle."""
    assert "publication_cycles" in PENDING_EVENTS_SQL
    assert "status = 'active'" in PENDING_EVENTS_SQL


def test_token_auth_cookie_secure_in_production() -> None:
    """SEC-001: Token auth cookie must have secure=True when in production or on https."""
    client = TestClient(app, base_url="https://testserver")
    test_settings = Settings(
        api_token="test_secret_token_12345",
        env="production",
        database_url="postgresql://user:pass@localhost:5432/db",
    )
    with patch("politikdesk.api.main.get_settings", return_value=test_settings):
        # Query param auth on https request
        resp = client.get("/api/events/live", params={"token": "test_secret_token_12345"})
        # Should set cookie with Secure flag
        set_cookie = resp.headers.get("set-cookie", "")
        assert "pd_token=" in set_cookie
        assert "secure" in set_cookie.lower()
        assert "httponly" in set_cookie.lower()
        assert "samesite=lax" in set_cookie.lower()


def test_assigner_candidate_trace_outcome_types() -> None:
    """TYP-001: CandidateTrace outcome must be a valid CandidateOutcome literal."""
    valid_outcomes: list[CandidateOutcome] = [
        "accepted",
        "review",
        "below_t_low",
        "time_reject",
        "entity_reject",
        "entity_unverified",
        "indicator_reject",
    ]
    for outcome in valid_outcomes:
        trace = CandidateTrace(
            event_id=1,
            similarity=0.9,
            time_ok=True,
            entity_verdict="ok",
            entity_jaccard=0.5,
            shared_key_entities=("TCMB",),
            outcome=outcome,
            indicator_conflict=False,
        )
        assert trace.outcome == outcome
