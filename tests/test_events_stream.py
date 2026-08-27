"""Real-Time SSE & Redis PubSub Akış Testleri."""

import json

import pytest

from politikdesk.events_stream import publish_feed_event, sse_event_stream


def test_publish_feed_event_success(monkeypatch: pytest.MonkeyPatch) -> None:
    published_messages = []

    class MockRedis:
        def publish(self, channel, message):
            published_messages.append((channel, message))
            return 1

    import redis
    monkeypatch.setattr(redis, "from_url", lambda *args, **kwargs: MockRedis())

    ok = publish_feed_event("feed_update", {"processed": 3})
    assert ok is True
    assert len(published_messages) == 1
    channel, raw_msg = published_messages[0]
    assert channel == "politikdesk:stream"
    parsed = json.loads(raw_msg)
    assert parsed["event"] == "feed_update"
    assert parsed["payload"]["processed"] == 3


@pytest.mark.asyncio
async def test_sse_event_stream_direct(monkeypatch: pytest.MonkeyPatch) -> None:
    """Async generator'ın ilk bağlantı olayını ürettiğini test eder."""
    class MockPubSub:
        async def subscribe(self, channel):
            pass

        async def get_message(self, *args, **kwargs):
            return {"type": "message", "data": json.dumps({"event": "feed_update", "data": {"count": 1}})}

        async def unsubscribe(self, channel):
            pass

        async def close(self):
            pass

    class MockAsyncRedis:
        def pubsub(self):
            return MockPubSub()

        async def aclose(self):
            pass

    import redis.asyncio as aioredis
    monkeypatch.setattr(aioredis, "from_url", lambda *args, **kwargs: MockAsyncRedis())

    class MockRequest:
        def __init__(self):
            self.calls = 0

        async def is_disconnected(self):
            self.calls += 1
            return self.calls > 2

    gen = sse_event_stream(MockRequest())
    first_chunk = await anext(gen)
    assert "event: connected" in first_chunk
    assert "status" in first_chunk

    second_chunk = await anext(gen)
    assert "event: feed_update" in second_chunk
