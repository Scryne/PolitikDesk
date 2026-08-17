"""Editoryal Canlı Bildirimler ve SSE (Server-Sent Events) Testleri."""

from __future__ import annotations

import json
import queue

from politikdesk.web.live_events import (
    EventHub,
    LiveEventMessage,
    format_sse,
    sse_event_stream,
)


def test_event_hub_publish_and_receive() -> None:
    """EventHub abonelere olayları anında iletmeli."""
    test_hub = EventHub()
    q = test_hub.subscribe()

    test_hub.broadcast_critical_event(
        title="Sayıştay 2025 Raporu Açıklandı",
        category="denetim",
        salience_score=0.92,
        event_id=55,
    )

    msg = q.get_nowait()
    assert msg.event_type == "critical_event"
    assert msg.data["title"] == "Sayıştay 2025 Raporu Açıklandı"
    assert msg.data["salience_score"] == 0.92
    assert msg.data["event_id"] == 55

    test_hub.unsubscribe(q)


def test_format_sse_output() -> None:
    """SSE formatlayıcı geçerli W3C EventSource sözdizimi üretmeli."""
    msg = LiveEventMessage(
        event_type="promise_relation",
        data={"from": "Vaat A", "to": "İcraat B", "relation": "fulfils"},
        timestamp="2026-08-16T12:00:00Z",
    )

    sse_text = format_sse(msg)
    assert sse_text.startswith("event: promise_relation\ndata: {")
    assert sse_text.endswith("\n\n")

    parsed_json = json.loads(sse_text.split("data: ")[1].strip())
    assert parsed_json["type"] == "promise_relation"
    assert parsed_json["data"]["relation"] == "fulfils"


def test_sse_stream_generator_emits_ping_on_timeout() -> None:
    """Kanal boş kaldığında SSE akış üreteci keep-alive ping yaymalı."""
    q: queue.Queue[LiveEventMessage] = queue.Queue()
    generator = sse_event_stream(q, timeout=0.01)

    first_item = next(generator)
    assert "event: ping" in first_item
    assert "alive" in first_item


def test_sse_stream_cleanup_on_generator_close() -> None:
    """İstemci bağlantısı koptuğunda (generator kapatıldığında) abone hub'dan düşmeli."""
    from politikdesk.web.live_events import hub

    initial_count = hub.subscriber_count
    q = hub.subscribe()
    assert hub.subscriber_count == initial_count + 1

    gen = sse_event_stream(q, timeout=0.01)
    _ = next(gen)
    gen.close()

    assert hub.subscriber_count == initial_count


def test_event_hub_redis_publish_mock(monkeypatch) -> None:
    """EventHub Redis etkin olduğunda Redis kanalına da yayın yapmalı."""
    from unittest.mock import MagicMock

    mock_redis = MagicMock()
    test_hub = EventHub(enable_redis=True)
    monkeypatch.setattr(test_hub, "_get_redis", lambda: mock_redis)

    test_hub.broadcast_critical_event(
        title="Bütçe Görüşmeleri Başladı",
        category="meclis",
        salience_score=0.85,
        event_id=102,
    )

    mock_redis.publish.assert_called_once()
    args, _ = mock_redis.publish.call_args
    assert args[0] == "pd:live_events"
    payload = json.loads(args[1])
    assert payload["event_type"] == "critical_event"
    assert payload["data"]["title"] == "Bütçe Görüşmeleri Başladı"
    test_hub.close()


def test_event_hub_in_memory_fallback() -> None:
    """Redis devre dışı veya kapalıyken in-memory fallback sorunsuz çalışmalı."""
    test_hub = EventHub(enable_redis=False)
    q = test_hub.subscribe()

    test_hub.broadcast_relation_event(
        from_title="Vaat 1",
        to_title="İcraat 1",
        relation="contradicts",
        confidence=0.95,
    )

    msg = q.get_nowait()
    assert msg.event_type == "promise_relation"
    assert msg.data["relation"] == "contradicts"
    assert msg.data["confidence"] == 0.95

    test_hub.unsubscribe(q)
    test_hub.close()

