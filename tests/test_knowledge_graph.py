"""tests/test_knowledge_graph.py — Bilgi Grafı SVG Üretim Testleri."""

from __future__ import annotations

from politikdesk.web.ui.charts import render_knowledge_graph


def test_render_knowledge_graph_basic():
    nodes = [
        {"id": "simsek", "label": "Mehmet Şimşek", "type": "actor"},
        {"id": "hazine", "label": "Hazine Bakanlığı", "type": "institution"},
        {"id": "p1", "label": "Enflasyon Hedefi", "type": "promise"},
    ]
    links = [
        {"source": "simsek", "target": "hazine", "relation": "precedes", "label": "Bakan"},
        {"source": "simsek", "target": "p1", "relation": "fulfils", "label": "Taahhüt"},
    ]

    svg = render_knowledge_graph(nodes, links, width=800, height=400)
    assert "<svg" in svg
    assert "knowledge-graph" in svg
    assert "Mehmet Şimşek" in svg
    assert "Hazine Bakanlığı" in svg
    assert "Enflasyon Hedefi" in svg
    assert "line" in svg
    assert "circle" in svg


def test_render_knowledge_graph_empty():
    svg = render_knowledge_graph([], [])
    assert svg == ""


def test_render_knowledge_graph_contradict_dashed():
    nodes = [
        {"id": "a", "label": "Aktör A", "type": "actor"},
        {"id": "b", "label": "İcraat B", "type": "event"},
    ]
    links = [
        {"source": "a", "target": "b", "relation": "contradicts", "label": "Çelişki"},
    ]
    svg = render_knowledge_graph(nodes, links)
    assert 'stroke-dasharray="4 2"' in svg
