"""Boru hattı aşama sağlığı monitörü testleri (F4-05, B-78, S3).

Tüm boru hattı aşamalarının (embed, entities, cluster, claims, evidence, context,
political_relations, scheduler_match) ve nabızların (ingest, briefing, metrics, purge)
izleme bütünlüğünü ve çalışan işçilerle birebir SQL eşliğini test eder.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from politikdesk.evidence.rules import engine_version
from politikdesk.nlp.claims_pipeline import MAX_CLAIM_ATTEMPTS
from politikdesk.pipeline_health import (
    HEARTBEATS,
    STAGES,
    _classify,
    _heartbeat_report,
    check_and_log,
)
from politikdesk.political_memory.orchestrator import RELATION_ENGINE_VERSION


def test_stages_and_heartbeats_completeness() -> None:
    """Tüm kritik boru hattı adımları ve nabızları tanımlı olmalı."""
    stage_keys = [s.key for s in STAGES]
    expected_stages = [
        "embed",
        "entities",
        "cluster",
        "claims",
        "evidence",
        "context",
        "political_relations",
        "scheduler_match",
    ]
    assert stage_keys == expected_stages

    heartbeat_keys = [h.key for h in HEARTBEATS]
    expected_heartbeats = ["ingest", "briefing", "metrics", "purge"]
    assert heartbeat_keys == expected_heartbeats


def test_every_stage_and_heartbeat_has_hint_and_positive_threshold() -> None:
    for stage in (*STAGES, *HEARTBEATS):
        assert stage.key.strip(), "Aşama anahtarı boş olamaz"
        assert stage.label.strip(), f"{stage.key}: etiket boş"
        assert stage.hint.strip(), f"{stage.key}: ipucu boş"
        assert stage.threshold_hours > 0, f"{stage.key}: eşik sıfır veya negatif"


def test_claims_stage_predicate_parity_with_worker() -> None:
    """İzleyici claims yüklemi, nlp/claims_pipeline.py::PENDING_EVENTS_SQL ile tam uyumlu olmalı (F5-16)."""
    claims_stage = next(s for s in STAGES if s.key == "claims")

    # Temel SQL yapısı denetimi
    assert "e.merged_into_id IS NULL" in claims_stage.sql
    assert "e.article_count > 0" in claims_stage.sql
    assert "e.claims_attempted_at IS NULL" in claims_stage.sql
    assert "e.last_update_at > e.claims_attempted_at" in claims_stage.sql
    assert "NOT EXISTS (SELECT 1 FROM claims c WHERE c.event_id = e.id)" in claims_stage.sql
    assert "e.claims_attempt_count < %s" in claims_stage.sql

    # F5-16: NOT EXISTS (claims) bir AND dalı DEĞİL, OR'un içinde olmalıdır
    assert (
        "AND NOT EXISTS (SELECT 1 FROM claims c WHERE c.event_id = e.id)" not in claims_stage.sql
    ), "claims izleyicisinde F5-16 hatası: NOT EXISTS dış AND dalında olmamalı"

    assert claims_stage.get_params() == (MAX_CLAIM_ATTEMPTS,)


def test_evidence_stage_predicate_parity_with_worker() -> None:
    """İzleyici evidence yüklemi, evidence/pipeline.py::score_claims ile tam uyumlu olmalı (F5-17)."""
    evidence_stage = next(s for s in STAGES if s.key == "evidence")

    assert "status_reason IS NULL" in evidence_stage.sql
    assert "status_reason->>'engine_version' IS DISTINCT FROM %s" in evidence_stage.sql
    assert "SELECT 1 FROM evidence ev" in evidence_stage.sql
    assert "ev.claim_id = c.id" in evidence_stage.sql
    assert "ev.created_at > (c.status_reason->>'computed_at')::timestamptz" in evidence_stage.sql

    # Dinamik engine_version kontrolü
    assert evidence_stage.get_params() == (engine_version(),)


def test_political_relations_stage_params() -> None:
    """Siyasi ilişkiler aşaması doğru motor sürüm parametrelerini almalı."""
    stage = next(s for s in STAGES if s.key == "political_relations")
    assert stage.get_params() == (RELATION_ENGINE_VERSION, RELATION_ENGINE_VERSION)


@pytest.mark.parametrize(
    ("age", "threshold", "expected"),
    [
        (None, 2.0, "green"),
        (0.0, 2.0, "green"),
        (0.9, 2.0, "green"),
        (1.0, 2.0, "amber"),  # threshold * 0.5
        (1.9, 2.0, "amber"),
        (2.0, 2.0, "red"),
        (5.0, 2.0, "red"),
    ],
)
def test_classification_logic(age: float | None, threshold: float, expected: str) -> None:
    assert _classify(age, threshold) == expected


def test_heartbeat_report_handles_missing_last_at() -> None:
    beat = HEARTBEATS[0]

    class _Cur:
        def execute(self, *_a: object, **_k: object) -> None:
            pass

        def fetchone(self) -> dict[str, object]:
            return {"last_at": None}

    report = _heartbeat_report(_Cur(), beat)
    assert report.status == "amber"
    assert report.oldest_hours is None
    assert "Hiç kayıt yok" in report.hint


def test_heartbeat_report_clips_future_timestamp() -> None:
    beat = HEARTBEATS[0]
    future = datetime.now(UTC) + timedelta(hours=5)

    class _Cur:
        def execute(self, *_a: object, **_k: object) -> None:
            pass

        def fetchone(self) -> dict[str, object]:
            return {"last_at": future}

    report = _heartbeat_report(_Cur(), beat)
    assert report.oldest_hours == 0.0
    assert report.status == "green"


def test_check_and_log_runs_cleanly(monkeypatch) -> None:  # noqa: ANN001
    """alarms() boşken veya doluyken check_and_log düzgün sözlük listesi döndürmeli."""
    from politikdesk.pipeline_health import StageReport

    sample_report = [
        StageReport(
            key="claims",
            label="İddia çıkarımı",
            status="red",
            backlog=15,
            oldest_hours=8.5,
            threshold_hours=6.0,
            hint="LLM bütçesi kontrolü",
            kind="backlog",
        )
    ]

    monkeypatch.setattr("politikdesk.pipeline_health.alarms", lambda: sample_report)
    logged = check_and_log()
    assert len(logged) == 1
    assert logged[0]["key"] == "claims"
    assert logged[0]["status"] == "red"
