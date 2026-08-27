"""Gerçek Zamanlı Haber Odası Akışı (Server-Sent Events / SSE & Redis PubSub).

Boru hattında yeni bir olay kümelendiğinde, iddia doğrulandığında veya anomali
oluştuğunda web tarayıcısına 0ms gecikmeyle anlık canlı veri akışı (push) sağlar.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import redis
import redis.asyncio as aioredis
from fastapi import Request

from politikdesk.config import get_settings
from politikdesk.observability import get_logger

log = get_logger(__name__)

REDIS_CHANNEL = "politikdesk:stream"


def publish_feed_event(event_type: str, payload: dict[str, Any] | None = None) -> bool:
    """Redis PubSub kanalına senkron bildirim yayınlar (Celery worker içinden çağrılır)."""
    settings = get_settings()
    if not settings.redis_url:
        return False

    message = {
        "event": event_type,
        "payload": payload or {},
        "timestamp": datetime.now(UTC).isoformat(),
    }

    try:
        r = redis.from_url(settings.redis_url, socket_timeout=3.0)
        r.publish(REDIS_CHANNEL, json.dumps(message, ensure_ascii=False))
        return True
    except Exception as exc:  # noqa: BLE001
        log.debug("sse_publish_failed", error=str(exc), stream_event=event_type)
        return False


async def sse_event_stream(request: Request) -> AsyncGenerator[str, None]:
    """FastAPI StreamingResponse için Server-Sent Events (SSE) asenkron jeneratörü."""
    settings = get_settings()
    r = aioredis.from_url(settings.redis_url, socket_timeout=10.0)
    pubsub = r.pubsub()
    await pubsub.subscribe(REDIS_CHANNEL)

    # Başlangıç bağlantı bildirimi
    init_msg = json.dumps({"status": "connected", "time": datetime.now(UTC).isoformat()})
    yield f"event: connected\ndata: {init_msg}\n\n"

    try:
        while True:
            # İstemci tarayıcı sekmeyi kapattıysa sonlandır
            if await request.is_disconnected():
                break

            try:
                # 15 saniyeye kadar mesaj bekle
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=15.0,
                )
                if message and message.get("type") == "message":
                    raw_data = message.get("data")
                    if isinstance(raw_data, bytes):
                        raw_data = raw_data.decode("utf-8")
                    try:
                        parsed = json.loads(raw_data)
                        ev_name = parsed.get("event", "update")
                        data_str = json.dumps(parsed, ensure_ascii=False)
                        yield f"event: {ev_name}\ndata: {data_str}\n\n"
                    except Exception:
                        yield f"data: {raw_data}\n\n"
            except TimeoutError:
                # 15 saniyede bir kalp atışı (keep-alive heartbeat)
                yield f": heartbeat {datetime.now(UTC).isoformat()}\n\n"
            except asyncio.CancelledError:
                break
    finally:
        try:
            await pubsub.unsubscribe(REDIS_CHANNEL)
            await pubsub.close()
            await r.aclose()
        except Exception:
            pass
