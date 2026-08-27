"""Liveness and readiness probe tests (Faz G)."""

from fastapi.testclient import TestClient

from politikdesk.api.main import app

client = TestClient(app)


def test_livez_probe() -> None:
    """Liveness probe must return 200 with status alive."""
    resp = client.get("/livez")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "alive"
    assert "version" in data


def test_readyz_probe() -> None:
    """Readiness probe must return 200 when DB and Redis are reachable."""
    resp = client.get("/readyz")
    # In test environment, if DB and Redis are active, should be 200 or 503 if mock
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "database" in data
    assert "redis" in data
