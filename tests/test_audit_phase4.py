"""Phase 4 Production Hardening, Concurrency & Security Regression Tests.

Covers:
- AUDIT-001: Concurrency safety in event creation & article assignment
- AUDIT-002: SSRF defense against redirect bypasses, private IPs, loops
- AUDIT-003: Cross-vertical event merge invariant enforcement
- AUDIT-004: Read-first user lookup avoiding write transactions on GET requests
- AUDIT-005: Context query starvation guard and zero-relation audit tracking
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from politikdesk.clustering.assigner import ArticleFeatures, Assignment
from politikdesk.clustering.merger import MergeError, merge_events
from politikdesk.clustering.repository import assign_article, create_event
from politikdesk.context.related import link_related
from politikdesk.ingestion.adapters.manual import (
    ManualImportAdapter,
    UnsafeUrlError,
    validate_url,
)
from politikdesk.users import current_user_id


# ===========================================================================
# AUDIT-001 — Concurrency Safety in Clustering
# ===========================================================================
def test_create_event_aborts_and_prevents_orphan_when_already_assigned() -> None:
    """AUDIT-001: Makale başka bir worker tarafından kapılmışsa create_event rollback yapar."""
    article = ArticleFeatures(
        article_id=42,
        embedding=[0.1, 0.2, 0.3],
        entities=frozenset(),
        key_entities=frozenset(),
        published_at=datetime.now(UTC),
        vertical="macro_economy",
    )
    row = {"title": "Test Makale", "excerpt": "Özet metin"}

    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {"id": 100}
    # _attach_article içindeki UPDATE articles WHERE event_id IS NULL -> 0 satır güncellendi (yarış durumu)
    mock_cur.rowcount = 0

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch("politikdesk.clustering.repository.connection", return_value=mock_conn):
        result = create_event(article, row)
        # Olay oluşturma iptal edilmeli, None dönmeli ve transaction rollback edilmeli
        assert result is None
        assert mock_conn.rollback.called
        assert not mock_conn.commit.called


def test_assign_article_aborts_when_already_assigned() -> None:
    """AUDIT-001: Makale yarış koşumunda başka olaya atanmışsa assign_article rollback yapar."""
    article = ArticleFeatures(
        article_id=42,
        embedding=[0.1, 0.2, 0.3],
        entities=frozenset(),
        key_entities=frozenset(),
        published_at=datetime.now(UTC),
        vertical="macro_economy",
    )
    decision = Assignment(action="assign", event_id=99, similarity=0.95)

    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {"centroid": "[0.1,0.2,0.3]", "article_count": 2}
    # _attach_article rowcount = 0 (zaten atanmış)
    mock_cur.rowcount = 0

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch("politikdesk.clustering.repository.connection", return_value=mock_conn):
        assigned = assign_article(article, decision)
        assert assigned is False
        assert mock_conn.rollback.called
        assert not mock_conn.commit.called


# ===========================================================================
# AUDIT-002 — SSRF Defense & Redirect Security
# ===========================================================================
@pytest.mark.parametrize(
    "invalid_url",
    [
        "http://127.0.0.1:8000/admin",
        "http://localhost:3000",
        "http://0.0.0.0/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/internal",
        "http://172.16.0.10/status",
        "http://192.168.1.1/router",
        "http://[::1]:8080/",
        "http://intranet.local/secret",
        "http://server.internal/",
        "ftp://example.com/file",
        "file:///etc/passwd",
    ],
)
def test_validate_url_rejects_ssrf_and_private_targets(invalid_url: str) -> None:
    """AUDIT-002: validate_url tüm loopback, private IP ve geçersiz şemaları engeller."""
    with pytest.raises(UnsafeUrlError):
        validate_url(invalid_url)


def test_manual_import_adapter_blocks_redirect_to_internal_ip() -> None:
    """AUDIT-002: 302 yönlendirmesi iç ağ / metadata adresine gidiyorsa engellenir."""
    initial_url = "https://public-news.example.com/article"
    redirect_target = "http://169.254.169.254/latest/meta-data/"

    mock_response = MagicMock()
    mock_response.status_code = 302
    mock_response.headers = {"Location": redirect_target}

    mock_http = MagicMock()
    mock_http.get.return_value = mock_response

    adapter = ManualImportAdapter(http=mock_http)
    with (
        patch("politikdesk.ingestion.adapters.manual.validate_url", side_effect=[initial_url, UnsafeUrlError("Özel IP")]),
        pytest.raises(UnsafeUrlError),
    ):
        adapter.fetch_one(initial_url)


def test_manual_import_adapter_blocks_redirect_loop() -> None:
    """AUDIT-002: Yönlendirme döngüleri (A -> B -> A) tespit edilip engellenir."""
    url_a = "https://public-news.example.com/a"
    url_b = "https://public-news.example.com/b"

    resp_a = MagicMock(status_code=302, headers={"Location": url_b})
    resp_b = MagicMock(status_code=302, headers={"Location": url_a})

    mock_http = MagicMock()
    mock_http.get.side_effect = [resp_a, resp_b]

    adapter = ManualImportAdapter(http=mock_http)
    with (
        patch("politikdesk.ingestion.adapters.manual.validate_url", side_effect=lambda u: u),
        pytest.raises(UnsafeUrlError, match="Yönlendirme döngüsü"),
    ):
        adapter.fetch_one(url_a)


def test_manual_import_adapter_follows_safe_public_redirect() -> None:
    """AUDIT-002: Güvenli genel internet yönlendirmesi başarıyla tamamlanır."""
    url_a = "https://public-news.example.com/short"
    url_b = "https://public-news.example.com/full-article-123"

    resp_a = MagicMock(status_code=301, headers={"Location": url_b})
    resp_b = MagicMock(
        status_code=200,
        text="<html><head><title>Haber Başlığı</title></head><body>İçerik</body></html>",
        url=httpx.URL(url_b),
    )

    mock_http = MagicMock()
    mock_http.get.side_effect = [resp_a, resp_b]

    adapter = ManualImportAdapter(http=mock_http)
    with patch("politikdesk.ingestion.adapters.manual.validate_url", side_effect=lambda u: u):
        item = adapter.fetch_one(url_a)
        assert item.url == url_b
        assert item.title == "Haber Başlığı"


# ===========================================================================
# AUDIT-003 — Cross-Vertical Merge Boundary
# ===========================================================================
def test_merge_events_allows_same_vertical() -> None:
    """AUDIT-003: Aynı dikeydeki iki olay birleştirilebilir."""
    mock_events = {
        1: {"id": 1, "vertical": "legislation", "merged_into_id": None},
        2: {"id": 2, "vertical": "legislation", "merged_into_id": None},
    }

    mock_cur = MagicMock()
    mock_cur.fetchall.side_effect = [
        list(mock_events.values()),  # events query
        [{"id": 10}, {"id": 11}],  # articles query
        [],  # refresh vectors target
        [],  # refresh vectors source
    ]

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch("politikdesk.clustering.merger.connection", return_value=mock_conn):
        res = merge_events(source_event_id=1, target_event_id=2)
        assert res.source_event_id == 1
        assert res.target_event_id == 2
        assert mock_conn.commit.called


def test_merge_events_rejects_different_verticals() -> None:
    """AUDIT-003: Farklı dikeylerdeki olaylar birleştirilemez (MergeError fırlatır)."""
    mock_events = {
        1: {"id": 1, "vertical": "legislation", "merged_into_id": None},
        2: {"id": 2, "vertical": "macro_economy", "merged_into_id": None},
    }

    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = list(mock_events.values())

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with (
        patch("politikdesk.clustering.merger.connection", return_value=mock_conn),
        pytest.raises(MergeError, match="Farklı dikeylerdeki olaylar birleştirilemez"),
    ):
        merge_events(source_event_id=1, target_event_id=2)


# ===========================================================================
# AUDIT-004 — Read-First User Lookup Caching
# ===========================================================================
def test_current_user_id_read_first_skips_insert_for_existing_user() -> None:
    """AUDIT-004: Mevcut kullanıcı için yalnızca SELECT çalışır, INSERT yapılmaz."""
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {"id": 7}

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch("politikdesk.users.connection", return_value=mock_conn):
        uid = current_user_id()
        assert uid == 7
        assert mock_cur.execute.called
        # İlk sorgu SELECT olmalı
        first_sql = mock_cur.execute.call_args_list[0][0][0]
        assert "SELECT id FROM users" in first_sql
        # Sadece 1 sorgu (SELECT) yapılmış olmalı, INSERT çağrılmamalı
        assert len(mock_cur.execute.call_args_list) == 1
        assert not mock_conn.commit.called


def test_current_user_id_inserts_safely_when_user_not_found() -> None:
    """AUDIT-004: Kullanıcı yoksa INSERT ON CONFLICT ile oluşturulur."""
    mock_cur = MagicMock()
    # İlk fetchone (SELECT) -> None, ikinci fetchone (INSERT RETURNING) -> {"id": 9}
    mock_cur.fetchone.side_effect = [None, {"id": 9}]

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch("politikdesk.users.connection", return_value=mock_conn):
        uid = current_user_id()
        assert uid == 9
        assert len(mock_cur.execute.call_args_list) == 2
        insert_sql = mock_cur.execute.call_args_list[1][0][0]
        assert "INSERT INTO users" in insert_sql
        assert mock_conn.commit.called


# ===========================================================================
# AUDIT-005 — Context Query Starvation Guard
# ===========================================================================
def test_context_link_related_writes_audit_even_for_zero_relations() -> None:
    """AUDIT-005: 0 geçmiş bağ bulunan olay context_evaluated ile damgalanır."""
    mock_cur = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with (
        patch("politikdesk.context.related.find_related", return_value=[]),
        patch("politikdesk.context.related.connection", return_value=mock_conn),
        patch("politikdesk.audit.write") as mock_audit,
    ):
        linked = link_related(999)
        assert linked == 0
        assert mock_audit.called
        assert mock_audit.call_args[0][0] == "context_evaluated"
        assert mock_audit.call_args[0][1] == "events/999"
