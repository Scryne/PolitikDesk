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


# ===========================================================================
# Phase 2 Hardening Fixes (DEF-01 to DEF-07, IMP-01 to IMP-04)
# ===========================================================================
def test_def01_claims_pipeline_extracts_with_article_vertical() -> None:
    """DEF-01: claims_pipeline extract_claims çağrısına article vertical parametresini iletir."""
    from unittest.mock import MagicMock, patch

    from politikdesk.nlp import claims_pipeline

    mock_articles = [
        {
            "id": 1,
            "title": "TBMM Kanun Teklifi",
            "excerpt": "Genel Kurul toplandı.",
            "source_name": "TBMM",
            "tier": 1,
            "published_at": "2026-08-16T12:00:00Z",
            "vertical": "legislation",
        }
    ]

    mock_cur = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    mock_extract_result = MagicMock()
    mock_extract_result.extracted_by = "test-model+v1"
    mock_extract_result.claims = []
    mock_extract_result.rejected = []

    with (
        patch("politikdesk.nlp.claims_pipeline.pending_events", return_value=[100]),
        patch("politikdesk.nlp.claims_pipeline._articles_of", return_value=mock_articles),
        patch("politikdesk.nlp.claims_pipeline.connection", return_value=mock_conn),
        patch(
            "politikdesk.nlp.claims_pipeline.extract_claims", return_value=mock_extract_result
        ) as mock_extract,
        patch("politikdesk.nlp.claims.group_claims_by_source", return_value=[]),
        patch("politikdesk.nlp.claims_pipeline._persist", return_value=[]),
        patch(
            "politikdesk.nlp.opinion_classifier.classify_content_kind",
            return_value=MagicMock(kind="news"),
        ),
    ):
        claims_pipeline.run(limit=1, client=MagicMock())
        assert mock_extract.called
        call_kwargs = mock_extract.call_args.kwargs
        assert call_kwargs.get("vertical") == "legislation"


def test_def02_draft_request_accepts_accountability_angle() -> None:
    """DEF-02: DraftRequest modeli 'accountability' açısını kabul eder."""
    import pydantic

    from politikdesk.web.api import DraftRequest

    req = DraftRequest(angle="accountability")
    assert req.angle == "accountability"

    # Diğer geçerli açılar
    for angle in ("inform", "analyze", "critique"):
        assert DraftRequest(angle=angle).angle == angle  # type: ignore[arg-type]

    # Geçersiz açı 422 / ValidationError üretir
    with pytest.raises(pydantic.ValidationError):
        DraftRequest(angle="invalid_angle")  # type: ignore[arg-type]


def test_def03_budget_alert_monthly_suppression_window() -> None:
    """DEF-03: alert_if_needed aylık bütçe için 24*31 saat bastırma penceresi kullanır."""
    from unittest.mock import patch

    from politikdesk.config import Settings
    from politikdesk.llm.budget import BudgetGuard

    guard = BudgetGuard(
        settings=Settings(
            env="test",
            llm_daily_budget_usd=10.0,
            llm_monthly_budget_usd=100.0,
        )
    )

    fake_snapshot = {
        "daily_spent_usd": 9.0,
        "daily_cap_usd": 10.0,
        "daily_ratio": 0.9,
        "monthly_spent_usd": 90.0,
        "monthly_cap_usd": 100.0,
        "monthly_ratio": 0.9,
    }

    suppression_windows: dict[str, int] = {}

    def mock_exists(action: str, target: str, hours: int = 25) -> bool:
        suppression_windows[target] = hours
        return True

    with (
        patch.object(guard, "snapshot", return_value=fake_snapshot),
        patch("politikdesk.audit.exists_since", side_effect=mock_exists),
    ):
        guard.alert_if_needed(notify=False)

        daily_key = [k for k in suppression_windows if "daily" in k][0]
        monthly_key = [k for k in suppression_windows if "monthly" in k][0]

        assert suppression_windows[daily_key] == 25
        assert suppression_windows[monthly_key] == 24 * 31


def test_def04_promises_and_archive_views_render_event_route() -> None:
    """DEF-04: promises_view ve archive_view /event/{id} tekil rotasını kullanır."""
    from unittest.mock import patch

    from politikdesk.web.archive_view import archive_page
    from politikdesk.web.promises_view import promises_page

    mock_promise = [
        {
            "claim_id": 1,
            "claim_text": "Vaat metni",
            "evidence_status": "strongly_corroborated",
            "event_id": 42,
            "event_title": "Test Olayı",
            "first_reported_at": "2026-08-16T12:00:00Z",
            "speaker": "Bakan",
            "outcome_relation": "fulfils",
            "relation_status": "verified",
            "evidence_payload": {},
        }
    ]

    mock_archive = [
        {
            "draft_id": 10,
            "event_id": 42,
            "event_title": "Test Olayı",
            "angle": "inform",
            "body": "Taslak gövdesi",
            "user_action": "accepted",
            "created_at": "2026-08-16T12:00:00Z",
            "cited_claim_ids": [1],
            "is_grounded": True,
            "model": "claude-3-5",
            "prompt_version": "v1",
        }
    ]

    with (
        patch(
            "politikdesk.web.promises_view.mem_service.get_promise_tracker",
            return_value=mock_promise,
        ),
        patch("politikdesk.users.touch_last_seen"),
    ):
        resp = promises_page()
        body = resp.body.decode("utf-8")
        assert 'href="/event/42"' in body
        assert 'href="/events/42"' not in body

    with (
        patch("politikdesk.web.archive_view.list_archived_publications", return_value=mock_archive),
        patch("politikdesk.users.touch_last_seen"),
    ):
        resp_arch = archive_page()
        body_arch = resp_arch.body.decode("utf-8")
        assert 'href="/event/42"' in body_arch
        assert 'href="/events/42"' not in body_arch


def test_def05_twitter_adapter_is_registered() -> None:
    """DEF-05: TwitterAdapter adapter registry'ye kayıtlıdır."""
    import politikdesk.ingestion.adapters.twitter  # noqa: F401
    from politikdesk.ingestion.adapters.base import registry
    from politikdesk.ingestion.adapters.twitter import TwitterAdapter

    assert registry.get("twitter") is TwitterAdapter


def test_def06_sidebar_nav_includes_memory() -> None:
    """DEF-06: shell.py NAV tuple'ı /memory rotasını içerir."""
    from politikdesk.web.ui.shell import NAV

    work_desk_group = next(items for title, items in NAV if title == "Çalışma masası")
    routes = [href for href, label, icon in work_desk_group]
    assert "/memory" in routes


def test_def07_stemmer_suffix_tuples_are_unique() -> None:
    """DEF-07: cross_source_matcher ve relation_engine suffix tablolarında mükerrer kayıt yoktur."""
    from politikdesk.nlp import cross_source_matcher

    assert len(cross_source_matcher._COMMON_SUFFIXES) == len(
        set(cross_source_matcher._COMMON_SUFFIXES)
    )


def test_imp01_manual_adapter_http_client_enforces_ssrf_dns() -> None:
    """IMP-01: ManualImportAdapter HttpClient'ı enforce_ssrf=True ve resolve_dns=True ile kurar."""
    from politikdesk.ingestion.adapters.manual import ManualImportAdapter

    adapter = ManualImportAdapter()
    assert adapter.http.enforce_ssrf is True
    assert adapter.http.resolve_dns is True


def test_imp02_get_actor_memory_queries_event_entities() -> None:
    """IMP-02: get_actor_memory sorgusu event_entities tablosunu kontrol eder."""
    from unittest.mock import MagicMock, patch

    from politikdesk.political_memory.service import get_actor_memory

    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = []
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch("politikdesk.political_memory.service.connection", return_value=mock_conn):
        get_actor_memory("Ahmet")
        assert mock_cur.execute.called
        sql = mock_cur.execute.call_args_list[0][0][0]
        assert "event_entities" in sql


def test_imp03_scripts_ingest_has_memory_command() -> None:
    """IMP-03: scripts.ingest CLI aracı memory alt komutunu destekler."""
    from unittest.mock import patch

    from scripts import ingest

    with (
        patch("sys.argv", ["scripts.ingest", "memory", "--limit", "25"]),
        patch("scripts.ingest.cmd_memory", return_value=0) as mock_cmd,
    ):
        ret = ingest.main()
        assert ret == 0
        assert mock_cmd.called
        assert mock_cmd.call_args[0][0] == 25


def test_imp04_metric_value_status_defensive() -> None:
    """IMP-04: MetricValue.status bilinmeyen yön ve eksik metada güvenli 'no_data' döner."""
    from politikdesk.metrics import MetricValue

    mv_none = MetricValue(name="unknown_metric", value=None, sample_size=0)
    assert mv_none.status == "no_data"

    mv_unregistered = MetricValue(name="custom_metric", value=5.0, sample_size=10)
    assert mv_unregistered.status == "no_data"

    # Bilinen metrik
    mv_ok = MetricValue(name="time_to_understanding", value=5.0, sample_size=10)
    assert mv_ok.status == "ok"


def test_ops01_watchdog_expected_containers_parity() -> None:
    """OPS-01: scripts.watchdog EXPECTED_CONTAINERS pd-worker-llm'i kapsar ve check_deployment ile uyumludur."""
    from scripts.check_deployment import CONTAINERS as DEPLOYMENT_CONTAINERS
    from scripts.watchdog import EXPECTED_CONTAINERS

    assert "pd-worker-llm" in EXPECTED_CONTAINERS
    assert "pd-worker" in EXPECTED_CONTAINERS
    assert "pd-beat" in EXPECTED_CONTAINERS
    assert "pd-api" in EXPECTED_CONTAINERS
    assert "pd-db" in EXPECTED_CONTAINERS
    assert "pd-redis" in EXPECTED_CONTAINERS

    # check_deployment'in denetlediği tüm uygulama konteynerleri watchdog tarafından da beklenir
    for c in DEPLOYMENT_CONTAINERS:
        assert c in EXPECTED_CONTAINERS
