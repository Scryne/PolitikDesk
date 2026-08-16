"""Denetim düzeltmeleri (D02, D03, D04, D06, I01, I04, I06) için birim testleri."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.config import Settings
from politikdesk.ingestion.http import ca_bundle_path
from politikdesk.llm.budget import PostgresLedger


# ===========================================================================
# D02 — Config tekil dosya çözümlemesi
# ===========================================================================
def test_config_resolved_env_file() -> None:
    """Settings model_config içinde env_file tek seferde çözülmüş olmalı."""
    settings = Settings()
    assert settings.model_config.get("env_prefix") == "PD_"


# ===========================================================================
# D03 — PostgresLedger SQL injection beyaz liste denetimi
# ===========================================================================
def test_postgres_ledger_interval_whitelist() -> None:
    """PostgresLedger._sum_since yalnızca 'day' ve 'month' kabul eder."""
    ledger = PostgresLedger()
    with pytest.raises(ValueError, match="Geçersiz SQL interval"):
        ledger._sum_since("year; DROP TABLE llm_calls; --")


# ===========================================================================
# D04 — CA bundle güvenli kullanıcı dizini
# ===========================================================================
def test_ca_bundle_path_user_private_dir() -> None:
    """CA bundle genel /tmp altında değil, kullanıcıya özel önbellekte olmalı."""
    bundle_file = ca_bundle_path()
    assert Path(bundle_file).exists()
    assert "PolitikDesk" in bundle_file or ".cache" in bundle_file or "certifi" in bundle_file


# ===========================================================================
# I01 — API Token kimlik doğrulama middleware
# ===========================================================================
def test_token_auth_middleware_disabled_by_default() -> None:
    """PD_API_TOKEN boşken istekler doğrudan geçer."""
    client = TestClient(app)
    response = client.get("/health/live")
    assert response.status_code == 200


def test_token_auth_middleware_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    """PD_API_TOKEN ayarlıyken yetkisiz istekler 401/403 alır, doğru token ile geçer."""
    import politikdesk.api.main as api_main

    monkeypatch.setattr(api_main, "get_settings", lambda: Settings(api_token="gizli-token-123"))

    client = TestClient(app)

    # Sağlık uçları muaftır
    live_resp = client.get("/health/live")
    assert live_resp.status_code == 200

    # Korumalı uç belirteçsiz çağrılınca 401
    unauth_resp = client.get("/api/angles")
    assert unauth_resp.status_code == 401
    assert "Kimlik doğrulama gerekli" in unauth_resp.json()["detail"]

    # Yanlış belirteç 403
    forbidden_resp = client.get("/api/angles", headers={"Authorization": "Bearer yanlis-token"})
    assert forbidden_resp.status_code == 403

    # Doğru Bearer belirteci 200
    ok_bearer = client.get("/api/angles", headers={"Authorization": "Bearer gizli-token-123"})
    assert ok_bearer.status_code == 200

    # Doğru X-API-Token başlığı 200
    ok_header = client.get("/api/angles", headers={"X-API-Token": "gizli-token-123"})
    assert ok_header.status_code == 200


# ===========================================================================
# I06 — CSRF koruma middleware
# ===========================================================================
def test_csrf_protection_allows_safe_methods() -> None:
    """GET istekleri cross-origin olsa bile CSRF kontrolünden geçer."""
    client = TestClient(app)
    resp = client.get("/api/angles", headers={"Origin": "https://evil.com"})
    assert resp.status_code == 200


def test_csrf_protection_blocks_mismatched_origin() -> None:
    """POST/PUT isteklerinde Origin != Host ise 403 ile engellenir."""
    client = TestClient(app)
    resp = client.post(
        "/api/events/1/feedback",
        headers={"Origin": "https://evil-site.com", "Host": "localhost:8000"},
        json={"note": "saldiri"},
    )
    assert resp.status_code == 403
    assert "CSRF koruması" in resp.json()["detail"]


def test_csrf_protection_allows_matching_origin() -> None:
    """Origin == Host olduğunda istek geçer."""
    client = TestClient(app)
    resp = client.post(
        "/api/activity",
        headers={"Origin": "http://testserver", "Host": "testserver"},
        json={"kind": "page_view", "path": "/feed"},
    )
    # 204 No Content
    assert resp.status_code == 204


def test_csrf_protection_blocks_missing_origin_on_non_api_routes() -> None:
    """D02: Web UI/Form rotalarında Origin/Referer yoksa 403 ile engellenir."""
    client = TestClient(app)
    resp = client.post("/admin/sources/sync", json={})
    assert resp.status_code == 403
    assert "Origin veya Referer başlığı gerekli" in resp.json()["detail"]


def test_csrf_protection_allows_token_requests_without_origin() -> None:
    """D04: Token taşıyan istekler Origin başlığı olmasa da CSRF kontrolünden geçer."""
    client = TestClient(app)
    resp = client.post(
        "/api/activity",
        headers={"X-API-Token": "some-token"},
        json={"kind": "page_view", "path": "/feed"},
    )
    assert resp.status_code == 204


# ===========================================================================
# D03 — LLM _post_with_retry tüketilmiş denemelerde fırlatma
# ===========================================================================
def test_llm_post_with_retry_raises_on_exhausted_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """D03: _post_with_retry tüm denemeler tükendiğinde LLMHTTPError fırlatır."""
    import httpx

    from politikdesk.llm.client import LLMHTTPError, _OpenAICompatBackend

    backend = _OpenAICompatBackend(Settings(llm_max_retries=2))

    class _MockFailingClient:
        def post(self, *args, **kwargs):  # noqa: ANN002, ANN003
            request = httpx.Request("POST", "https://api.example.com/chat/completions")
            return httpx.Response(503, text="Service Unavailable", request=request)

    backend._http = _MockFailingClient()  # type: ignore[assignment]
    monkeypatch.setattr("time.sleep", lambda _: None)

    with pytest.raises(LLMHTTPError) as exc_info:
        backend._post_with_retry(
            "https://api.example.com/chat/completions",
            headers={},
            payload={"model": "test"},
        )
    assert exc_info.value.status_code == 503
    assert "Service Unavailable" in exc_info.value.body


# ===========================================================================
# DEF-01 / IMP-02 — Multi-Vertical Ingestion & Provenance
# ===========================================================================
def test_multi_vertical_ingestion_preserves_legislation_articles() -> None:
    """DEF-01: Yasama kaynaklarından gelen makaleler topic filtreden düşmez."""
    from datetime import UTC, datetime
    from unittest.mock import MagicMock, patch

    from politikdesk.ingestion.models import IngestionStats, RawItem
    from politikdesk.ingestion.pipeline import Pipeline
    from politikdesk.ingestion.repository import SourceRow

    source = SourceRow(
        id=99,
        slug="tbmm",
        name="TBMM",
        tier=1,
        kind="official",
        independence_group="tbmm",
        access_method="official_feed",
        tos_status="allowed",
        adapter="tbmm",
        base_url="https://tbmm.gov.tr",
        feed_url="https://tbmm.gov.tr/rss",
        extra_feeds=[],
        keyword_filter=[],
        topics=["yasama_sureci"],
        is_active=True,
        is_wire_reference=False,
        vertical="legislation",
    )

    item = RawItem(
        source_slug="tbmm",
        url="https://tbmm.gov.tr/kanun-teklifi-123",
        title="TBMM Genel Kurulu'nda yeni kanun teklifi görüşülüyor",
        published_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        summary="TBMM Genel Kurulu'nda torba kanun teklifi maddeleri kabul edildi.",
        guid="tbmm-123",
    )

    pipe = Pipeline(enforce_topic_scope=True)
    decision = MagicMock(store_excerpt=True)
    stats = IngestionStats()

    # repository.insert_article ve load_dedup_window mock
    mock_window = MagicMock()
    mock_window.hashes = {}
    mock_window.simhashes = []
    mock_window.texts = {}

    with (
        patch("politikdesk.ingestion.repository.load_dedup_window", return_value=mock_window),
        patch("politikdesk.ingestion.repository.insert_article", return_value=123) as mock_insert,
    ):
        result_stats = pipe._store_items([item], source, decision, stats)
        assert result_stats.filtered_out == 0
        assert result_stats.stored == 1
        assert mock_insert.called
        inserted_article = mock_insert.call_args[0][0]
        assert inserted_article.vertical == "legislation"
        assert "yasama_sureci" in inserted_article.topics


# ===========================================================================
# DEF-02 — Clustering Repository Vertical Loading
# ===========================================================================
def test_clustering_load_features_preserves_vertical() -> None:
    """DEF-02: load_features makalenin vertical alanını ArticleFeatures'a aktarır."""
    from datetime import UTC, datetime
    from unittest.mock import patch

    from politikdesk.clustering.repository import load_features

    mock_row = {
        "id": 42,
        "title": "TBMM Yeni Kanun",
        "excerpt": "Görüşmeler tamamlandı.",
        "published_at": datetime(2026, 8, 15, 10, 0, tzinfo=UTC),
        "first_seen_at": datetime(2026, 8, 15, 10, 0, tzinfo=UTC),
        "embedding": "[0.1, 0.2, 0.3]",
        "vertical": "legislation",
    }

    with patch(
        "politikdesk.clustering.repository._entity_sets", return_value=(frozenset(), frozenset())
    ):
        features = load_features(mock_row)
        assert features.vertical == "legislation"
        assert features.article_id == 42


# ===========================================================================
# DEF-03 — Political Memory Reprocessing Starvation Guard
# ===========================================================================
def test_political_relations_orchestrator_prevents_starvation_loop() -> None:
    """DEF-03: Sıfır ilişki bulunan olay audit_log'a yazılır ve sonraki turda elenir."""
    from datetime import UTC, datetime
    from unittest.mock import MagicMock, patch

    from politikdesk.political_memory.orchestrator import evaluate_and_record_relations_for_event

    mock_src_row = {
        "id": 999,
        "title": "Test Olay",
        "first_reported_at": datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        "vertical": "legislation",
        "topic_tags": [],
    }

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = mock_src_row
    mock_cursor.fetchall.return_value = []

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with (
        patch("politikdesk.political_memory.orchestrator.connection", return_value=mock_conn),
        patch("politikdesk.audit.write") as mock_audit,
    ):
        results = evaluate_and_record_relations_for_event(999, candidate_events=[])
        assert results == []
        assert mock_audit.called
        assert mock_audit.call_args[0][0] == "political_relations_evaluated"
        assert mock_audit.call_args[0][1] == "events/999"


# ===========================================================================
# DEF-05 — Pipeline Health Heartbeat Datetime Handling
# ===========================================================================
def test_pipeline_health_heartbeat_handles_naive_and_aware_datetime() -> None:
    """DEF-05: _heartbeat_report hem naive hem timezone-aware timestamp ile çökmeden çalışır."""
    from datetime import UTC, datetime, timedelta
    from unittest.mock import MagicMock

    from politikdesk.pipeline_health import Heartbeat, _heartbeat_report

    beat = Heartbeat(
        key="test_beat",
        label="Test",
        threshold_hours=2.0,
        sql="SELECT max(created_at) AS last_at FROM test_table",
        hint="Test hint",
    )

    # 1. Aware datetime
    aware_now = datetime.now(UTC) - timedelta(minutes=30)
    mock_cur1 = MagicMock()
    mock_cur1.fetchone.return_value = {"last_at": aware_now}
    rep = _heartbeat_report(mock_cur1, beat)
    assert rep.status == "green"
    assert rep.oldest_hours is not None and rep.oldest_hours < 1.0

    # 2. Naive datetime (DB'den tzinfo olmadan döndüğünde)
    naive_now = (datetime.now(UTC) - timedelta(minutes=30)).replace(tzinfo=None)
    mock_cur2 = MagicMock()
    mock_cur2.fetchone.return_value = {"last_at": naive_now}
    rep2 = _heartbeat_report(mock_cur2, beat)
    assert rep2.status == "green"
    assert rep2.oldest_hours is not None and rep2.oldest_hours < 1.0


# ===========================================================================
# IMP-03 — Admin Articles Vertical Filter
# ===========================================================================
def test_admin_articles_vertical_filter_query() -> None:
    """IMP-03: /admin/articles uç noktası vertical parametresini sorguya ekler."""
    from unittest.mock import MagicMock, patch

    from politikdesk.admin.router import list_articles

    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = []
    mock_cur.fetchone.return_value = {"total": 0}

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch("politikdesk.db.connection", return_value=mock_conn):
        list_articles(vertical="legislation")
        assert mock_cur.execute.called
        sql_called = mock_cur.execute.call_args_list[0][0][0]
        params_called = mock_cur.execute.call_args_list[0][0][1]
        assert "a.vertical = %s" in sql_called
        assert "legislation" in params_called
