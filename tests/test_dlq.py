"""Celery Dead-Letter Queue (DLQ) Testleri."""

from __future__ import annotations

import pytest

from politikdesk.db import connection
from politikdesk.dlq import (
    discard_dead_letter_task,
    get_dlq_summary,
    list_dead_letter_tasks,
    record_dead_letter_task,
    requeue_dead_letter_task,
    retry_all_pending,
)


@pytest.fixture(autouse=True)
def _clean_dlq():
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM dead_letter_tasks")
        conn.commit()
    yield
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM dead_letter_tasks")
        conn.commit()


def test_record_and_list_dlq_task() -> None:
    task_id = "test-task-12345"
    entry_id = record_dead_letter_task(
        task_id=task_id,
        task_name="politikdesk.test_task",
        args=[1, "deneme"],
        kwargs={"foo": "bar"},
        exception=ValueError("Gecersiz parametre"),
        traceback_str="Traceback (most recent call last):\n  ...",
        retry_count=3,
    )
    assert entry_id > 0

    tasks = list_dead_letter_tasks(limit=10, status="pending")
    assert len(tasks) == 1
    t = tasks[0]
    assert t["task_id"] == task_id
    assert t["task_name"] == "politikdesk.test_task"
    assert t["exception_type"] == "ValueError"
    assert "Gecersiz parametre" in t["exception_message"]
    assert t["status"] == "pending"

    summary = get_dlq_summary()
    assert summary["pending"] == 1
    assert summary["total"] == 1


def test_discard_dlq_task() -> None:
    entry_id = record_dead_letter_task(
        task_id="discard-123",
        task_name="politikdesk.discard_me",
        exception=RuntimeError("Gecici hata"),
    )

    ok = discard_dead_letter_task(entry_id)
    assert ok is True

    pending = list_dead_letter_tasks(status="pending")
    assert len(pending) == 0

    all_tasks = list_dead_letter_tasks(status="all")
    assert len(all_tasks) == 1
    assert all_tasks[0]["status"] == "discarded"
    assert all_tasks[0]["resolved_at"] is not None


def test_requeue_dlq_task(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_tasks = []

    class MockCeleryApp:
        def send_task(self, name, args=None, kwargs=None):
            sent_tasks.append((name, args, kwargs))

    import politikdesk.worker as worker_mod
    monkeypatch.setattr(worker_mod, "app", MockCeleryApp())

    entry_id = record_dead_letter_task(
        task_id="retry-123",
        task_name="politikdesk.retry_me",
        args=[42],
        kwargs={"key": "val"},
        exception=TimeoutError("Zaman asimi"),
    )

    ok = requeue_dead_letter_task(entry_id)
    assert ok is True
    assert len(sent_tasks) == 1
    assert sent_tasks[0][0] == "politikdesk.retry_me"
    assert sent_tasks[0][1] == [42]
    assert sent_tasks[0][2] == {"key": "val"}

    summary = get_dlq_summary()
    assert summary["retried"] == 1
    assert summary["pending"] == 0


def test_retry_all_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_tasks = []

    class MockCeleryApp:
        def send_task(self, name, args=None, kwargs=None):
            sent_tasks.append(name)

    import politikdesk.worker as worker_mod
    monkeypatch.setattr(worker_mod, "app", MockCeleryApp())

    record_dead_letter_task(task_id="r1", task_name="t1", exception=RuntimeError("e1"))
    record_dead_letter_task(task_id="r2", task_name="t2", exception=RuntimeError("e2"))

    count = retry_all_pending()
    assert count == 2
    assert len(sent_tasks) == 2
    assert get_dlq_summary()["pending"] == 0
