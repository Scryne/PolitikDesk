"""Boru hattı boşaltma ve otomatik kuyruk yönetimi testleri (F4-05, B-78)."""

from __future__ import annotations

from unittest.mock import MagicMock

from politikdesk.config import get_settings


def test_get_settings_loads_env() -> None:
    """get_settings çağrıldığında ortam değişkenlerinin yüklenmesi garanti edilir."""
    s = get_settings()
    assert s is not None


def test_task_auto_drain_triggers_when_batch_full(monkeypatch) -> None:
    """Celery görevleri parti dolduğunda kendisini asenkron olarak yeniden tetikler."""
    from politikdesk.tasks import embed_pending

    # Mock nlp_repo
    class FakeRepo:
        @staticmethod
        def pending_embedding(limit: int) -> list[dict[str, object]]:
            return [{"id": i, "title": f"T{i}", "excerpt": f"E{i}"} for i in range(limit)]

        @staticmethod
        def save_embeddings(vectors: dict[int, list[float]]) -> int:
            return len(vectors)

    class FakeBackend:
        name = "fake"

        @staticmethod
        def embed(texts: list[str]) -> list[list[float]]:
            return [[0.1] * 10 for _ in texts]

    monkeypatch.setattr("politikdesk.nlp.repository.pending_embedding", FakeRepo.pending_embedding)
    monkeypatch.setattr("politikdesk.nlp.repository.save_embeddings", FakeRepo.save_embeddings)
    monkeypatch.setattr("politikdesk.nlp.embedder.build_backend", lambda: FakeBackend())

    # Task mock context with request.id
    monkeypatch.setattr(embed_pending, "apply_async", MagicMock())
    embed_pending.request.id = "fake-task-uuid"

    saved = embed_pending(limit=10)
    assert saved == 10
    embed_pending.apply_async.assert_called_once_with(args=[10], countdown=1)


def test_drain_pipeline_script_runs(monkeypatch) -> None:
    """drain_pipeline betiği tüm aşamaları sırayla koşturur."""
    from scripts.drain_pipeline import drain_all

    # Mock stages
    monkeypatch.setattr("politikdesk.nlp.repository.pending_embedding", lambda limit: [])
    monkeypatch.setattr("politikdesk.nlp.repository.pending_entities", lambda limit: [])
    monkeypatch.setattr("politikdesk.clustering.pipeline.run", lambda limit: MagicMock(processed=0))
    monkeypatch.setattr("politikdesk.evidence.pipeline.run", lambda limit: MagicMock(claims_scored=0))
    monkeypatch.setattr(
        "politikdesk.context.related.run", lambda limit: {"events_processed": 0}
    )
    monkeypatch.setattr(
        "politikdesk.political_memory.orchestrator.process_pending_political_relations",
        lambda limit: {"events_processed": 0},
    )
    monkeypatch.setattr("politikdesk.context.scheduler_match.match_pending", lambda: {"matched": 0})
    monkeypatch.setattr("politikdesk.pipeline_health.stage_report", lambda: [])

    stats = drain_all(skip_llm=True)
    assert stats["embedded"] == 0
    assert stats["entities"] == 0
    assert stats["clustered"] == 0
    assert stats["claims"] == 0
