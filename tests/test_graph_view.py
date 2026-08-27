"""tests/test_graph_view.py — Siyasi İlişki Grafı Ekranı ve Veri API Testleri."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.web.ui.tokens import DARK

client = TestClient(app)


def test_graph_page_endpoint():
    res = client.get("/graph")
    assert res.status_code == 200
    assert "Siyasi İlişki ve İstihbarat Grafı" in res.text
    assert "pd-graph-canvas" in res.text
    assert "Düğüm Detayı" in res.text
    assert "Graf Lejantı" in res.text


def test_graph_data_endpoint():
    mock_shifts = [
        {
            "id": 1,
            "actor_name": "Mehmet Şimşek",
            "shift_type": "reversal",
            "topic_or_metric": "Faiz",
            "earlier_event_id": 10,
            "earlier_event_title": "Faiz İndirimi Beklentisi",
            "later_event_id": 20,
            "later_event_title": "Sıkı Para Politikası Vurgusu",
            "time_span_days": 180,
            "confidence": 0.90,
            "status": "open",
        }
    ]

    mock_relations = [
        {
            "id": 100,
            "from_event_id": 10,
            "to_event_id": 30,
            "relation": "updates",
            "similarity": 0.82,
            "from_title": "Faiz İndirimi Beklentisi",
            "to_title": "TCMB Yeni PPK Kararı",
        }
    ]

    with patch("politikdesk.web.graph_view.connection") as mock_conn:
        mock_cur = MagicMock()
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = (
            mock_cur
        )
        # 1st fetch: shifts, 2nd fetch: relations
        mock_cur.fetchall.side_effect = [mock_shifts, mock_relations]

        res = client.get("/api/graph/data")
        assert res.status_code == 200
        data = res.json()

        assert "nodes" in data
        assert "links" in data
        assert "stats" in data

        nodes = data["nodes"]
        node_ids = {n["id"] for n in nodes}
        assert "actor:Mehmet Şimşek" in node_ids
        assert "event:10" in node_ids
        assert "event:20" in node_ids

        actor_node = next(n for n in nodes if n["id"] == "actor:Mehmet Şimşek")
        assert actor_node["type"] == "actor"
        assert actor_node["color"] == DARK["color-chart-1"]


def test_graph_data_live_db_execution():
    """Verifies that get_graph_data executes without cursor closure errors against real database."""
    res = client.get("/api/graph/data?limit=25")
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "links" in data
    assert "stats" in data
    assert isinstance(data["stats"]["node_count"], int)
