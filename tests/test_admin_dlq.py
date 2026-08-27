"""Admin Dead-Letter Queue (DLQ) Uç Noktası Testleri."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.config import get_settings
from politikdesk.db import connection
from politikdesk.dlq import record_dead_letter_task


@pytest.fixture(autouse=True)
def _clean_dlq_records():
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM dead_letter_tasks")
        conn.commit()
    yield
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM dead_letter_tasks")
        conn.commit()


def test_admin_dlq_list_and_discard() -> None:
    settings = get_settings()
    headers = {"Origin": "http://testserver"}
    if settings.api_token:
        headers["Authorization"] = f"Bearer {settings.api_token}"
    client = TestClient(app)

    entry_id = record_dead_letter_task(
        task_id="admin-test-1",
        task_name="politikdesk.sample_task",
        exception=ValueError("Gecersiz girdi"),
    )

    # Listele
    res = client.get("/admin/dlq", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["summary"]["pending"] == 1
    assert len(data["tasks"]) == 1

    # Discard / Arşivle
    res_discard = client.post(f"/admin/dlq/{entry_id}/discard", headers=headers)
    assert res_discard.status_code == 200
    assert res_discard.json()["status"] == "discarded"

    # Tekrar listele
    res2 = client.get("/admin/dlq?status=pending", headers=headers)
    assert len(res2.json()["tasks"]) == 0


def test_admin_dlq_retry_all(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    headers = {"Origin": "http://testserver"}
    if settings.api_token:
        headers["Authorization"] = f"Bearer {settings.api_token}"
    client = TestClient(app)

    class MockCeleryApp:
        def send_task(self, name, args=None, kwargs=None):
            pass

    import politikdesk.worker as worker_mod
    monkeypatch.setattr(worker_mod, "app", MockCeleryApp())

    record_dead_letter_task(task_id="t1", task_name="politikdesk.t1", exception=RuntimeError("e1"))
    record_dead_letter_task(task_id="t2", task_name="politikdesk.t2", exception=RuntimeError("e2"))

    res = client.post("/admin/dlq/retry-all", headers=headers)
    assert res.status_code == 200
    assert res.json()["requeued_count"] == 2
