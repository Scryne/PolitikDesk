"""Prometheus OpenMetrics Telemetri Exporter Testleri."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.api.metrics_exporter import generate_prometheus_metrics

client = TestClient(app)


@pytest.mark.db
def test_generate_prometheus_metrics_format() -> None:
    """Prometheus metrik metin formatı doğrulaması."""
    output = generate_prometheus_metrics()

    assert isinstance(output, str)
    assert "# HELP politikdesk_uptime_seconds" in output
    assert "# TYPE politikdesk_uptime_seconds gauge" in output
    assert "politikdesk_uptime_seconds" in output
    assert "politikdesk_queue_depth{" in output
    assert "politikdesk_circuits_total" in output
    assert "politikdesk_llm_budget_used_usd" in output
    assert "politikdesk_backup_age_hours" in output
    assert "politikdesk_backup_healthy" in output
    assert "politikdesk_drill_age_hours" in output
    assert "politikdesk_drill_healthy" in output
    assert "politikdesk_pipeline_stage_backlog{" in output


def test_metrics_http_endpoint() -> None:
    """GET /metrics HTTP uç noktası testi."""
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "politikdesk_uptime_seconds" in resp.text
    assert "politikdesk_backup_age_hours" in resp.text
    assert "politikdesk_backup_healthy" in resp.text
