"""Editoryal Canlı Bildirimler ve SSE (Server-Sent Events) Olay Akışı (Spec v3.5 §14).

Bu modül, kritik siyasi gelişmeler, yeni Sayıştay/TBMM raporları, vaat çelişkileri
ve yüksek salience'lı olaylar meydana geldiğinde editoryal arayüze anlık SSE bildirimi
sağlar.
"""

from __future__ import annotations

import contextlib
import json
import queue
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from politikdesk.config import get_settings
from politikdesk.observability import get_logger

log = get_logger(__name__)

REDIS_CHANNEL = "pd:live_events"


@dataclass(frozen=True)
class LiveEventMessage:
    event_type: str  # "critical_event" | "promise_relation" | "breaking_report" | "ping"
    data: dict[str, Any]
    timestamp: str


class EventHub:
    """Çoklu worker (Celery/Uvicorn) uyumlu Redis Pub/Sub ve iç bellek olay dağıtıcısı."""

    def __init__(self, *, enable_redis: bool = True) -> None:
        self._subscribers: list[queue.Queue[LiveEventMessage]] = []
        self._lock = threading.Lock()
        self._enable_redis = enable_redis
        self._redis_client: Any = None
        self._redis_listener_thread: threading.Thread | None = None
        self._redis_stop_event = threading.Event()

    @property
    def subscriber_count(self) -> int:
        """Aktif SSE dinleyici sayısı."""
        with self._lock:
            return len(self._subscribers)

    def _get_redis(self) -> Any:
        if not self._enable_redis:
            return None
        if self._redis_client is None:
            try:
                import redis

                settings = get_settings()
                if not settings.redis_url:
                    return None
                self._redis_client = redis.Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_timeout=2.0,
                )
            except Exception as exc:  # noqa: BLE001
                log.debug("redis_init_failed", error=str(exc))
                return None
        return self._redis_client

    def _broadcast_local(self, msg: LiveEventMessage) -> None:
        """Süreç içi yerel abonelere mesaj iletir."""
        with self._lock:
            dead_queues = []
            for q in self._subscribers:
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    dead_queues.append(q)
            for dead in dead_queues:
                if dead in self._subscribers:
                    self._subscribers.remove(dead)

    def _redis_listener_loop(self) -> None:
        """Redis Pub/Sub kanalını dinleyen arka plan iş parçacığı."""
        backoff = 1.0
        while not self._redis_stop_event.is_set():
            pubsub = None
            try:
                r = self._get_redis()
                if r is None:
                    time.sleep(2.0)
                    continue

                pubsub = r.pubsub()
                pubsub.subscribe(REDIS_CHANNEL)
                log.debug("redis_pubsub_subscribed", channel=REDIS_CHANNEL)
                backoff = 1.0

                while not self._redis_stop_event.is_set():
                    raw_msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if raw_msg and raw_msg.get("type") == "message":
                        try:
                            payload = json.loads(raw_msg["data"])
                            event_type = payload.get("event_type", "unknown")
                            data = payload.get("data", {})
                            ts = payload.get("timestamp", datetime.now(UTC).isoformat())
                            # Sadece başka süreçlerden gelen mesajları yerel abonelere ilet
                            msg = LiveEventMessage(event_type=event_type, data=data, timestamp=ts)
                            self._broadcast_local(msg)
                        except Exception as exc:  # noqa: BLE001
                            log.debug("redis_message_parse_failed", error=str(exc))
            except Exception as exc:  # noqa: BLE001
                log.debug("redis_listener_disconnected", error=str(exc), retry_in=backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 15.0)
            finally:
                if pubsub:
                    with contextlib.suppress(Exception):
                        pubsub.close()

    def _ensure_listener_started(self) -> None:
        if not self._enable_redis:
            return
        with self._lock:
            if self._redis_listener_thread is None or not self._redis_listener_thread.is_alive():
                self._redis_stop_event.clear()
                self._redis_listener_thread = threading.Thread(
                    target=self._redis_listener_loop,
                    name="pd-redis-events-listener",
                    daemon=True,
                )
                self._redis_listener_thread.start()

    def subscribe(self) -> queue.Queue[LiveEventMessage]:
        """Yeni bir SSE dinleyicisi kaydeder ve gerekirse Redis dinleyicisini başlatır."""
        q: queue.Queue[LiveEventMessage] = queue.Queue(maxsize=100)
        with self._lock:
            self._subscribers.append(q)
        self._ensure_listener_started()
        log.debug("sse_subscriber_connected", total=len(self._subscribers))
        return q

    def unsubscribe(self, q: queue.Queue[LiveEventMessage]) -> None:
        """Ayrılan SSE dinleyicisini siler."""
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)
        log.debug("sse_subscriber_disconnected", remaining=self.subscriber_count)

    def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Tüm aktif dinleyicilere anlık mesaj iletir (yerel + Redis Pub/Sub)."""
        msg = LiveEventMessage(
            event_type=event_type,
            data=data,
            timestamp=datetime.now(UTC).isoformat(),
        )
        # 1. Yerel abonelere anında ilet
        self._broadcast_local(msg)

        # 2. Çoklu worker / Celery süreçleri için Redis Pub/Sub'a yaz
        if self._enable_redis:
            try:
                r = self._get_redis()
                if r is not None:
                    payload = json.dumps({
                        "event_type": event_type,
                        "data": data,
                        "timestamp": msg.timestamp,
                    })
                    r.publish(REDIS_CHANNEL, payload)
            except Exception as exc:  # noqa: BLE001
                log.debug("redis_publish_failed_fallback_local", error=str(exc))

    def broadcast_critical_event(
        self,
        title: str,
        category: str,
        salience_score: float,
        *,
        event_id: int | None = None,
    ) -> None:
        """Kritik olay yayını (Sayıştay kamu zararı, TBMM oylama, yüksek teyit)."""
        self.publish(
            "critical_event",
            {
                "title": title,
                "category": category,
                "salience_score": round(salience_score, 2),
                "event_id": event_id,
            },
        )

    def broadcast_relation_event(
        self,
        from_title: str,
        to_title: str,
        relation: str,
        confidence: float,
    ) -> None:
        """Vaat veya duruş çelişkisi yayını (contradicts, fulfils, updates)."""
        self.publish(
            "promise_relation",
            {
                "from_title": from_title,
                "to_title": to_title,
                "relation": relation,
                "confidence": round(confidence, 2),
            },
        )

    def close(self) -> None:
        """Dinleyici iş parçacığını ve kaynakları kapatır."""
        self._redis_stop_event.set()
        if self._redis_client:
            with contextlib.suppress(Exception):
                self._redis_client.close()


# Global tekil hub örneği
hub = EventHub()


def format_sse(msg: LiveEventMessage) -> str:
    """SSE formatında satır üretir: `event: ...\ndata: ...\n\n`."""
    payload = json.dumps({"type": msg.event_type, "data": msg.data, "timestamp": msg.timestamp})
    return f"event: {msg.event_type}\ndata: {payload}\n\n"


def sse_event_stream(q: queue.Queue[LiveEventMessage], timeout: float = 15.0) -> Iterator[str]:
    """SSE akış üreteci: veri geldikçe yield eder, boşlukta ping atar.

    İstemci bağlantısı koptuğunda (GeneratorExit / CancelledError)
    `finally` bloğu aboneliği EventHub'dan mutlak olarak düşürür.
    """
    try:
        while True:
            try:
                msg = q.get(timeout=timeout)
                yield format_sse(msg)
            except queue.Empty:
                # Keep-alive ping
                ping_msg = LiveEventMessage(
                    event_type="ping",
                    data={"status": "alive"},
                    timestamp=datetime.now(UTC).isoformat(),
                )
                yield format_sse(ping_msg)
    except (GeneratorExit, BaseException) as exc:
        log.debug("sse_stream_closed", reason=type(exc).__name__)
        raise
    finally:
        hub.unsubscribe(q)

