"""Editoryal Canlı Bildirimler ve SSE (Server-Sent Events) Olay Akışı (Spec v3.5 §14).

Bu modül, kritik siyasi gelişmeler, yeni Sayıştay/TBMM raporları, vaat çelişkileri
ve yüksek salience'lı olaylar meydana geldiğinde editoryal arayüze anlık SSE bildirimi
sağlar.
"""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from politikdesk.observability import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class LiveEventMessage:
    event_type: str  # "critical_event" | "promise_relation" | "breaking_report" | "ping"
    data: dict[str, Any]
    timestamp: str


class EventHub:
    """İç bellek olay dağıtıcısı ve SSE yayıncısı."""

    def __init__(self) -> None:
        self._subscribers: list[queue.Queue[LiveEventMessage]] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue[LiveEventMessage]:
        """Yeni bir SSE dinleyicisi kaydeder."""
        q: queue.Queue[LiveEventMessage] = queue.Queue(maxsize=100)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[LiveEventMessage]) -> None:
        """Ayrılan SSE dinleyicisini siler."""
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Tüm aktif dinleyicilere anlık mesaj iletir."""
        msg = LiveEventMessage(
            event_type=event_type,
            data=data,
            timestamp=datetime.now(UTC).isoformat(),
        )
        with self._lock:
            dead_queues = []
            for q in self._subscribers:
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    dead_queues.append(q)
            for dead in dead_queues:
                self._subscribers.remove(dead)

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


# Global tekil hub örneği
hub = EventHub()


def format_sse(msg: LiveEventMessage) -> str:
    """SSE formatında satır üretir: `event: ...\ndata: ...\n\n`."""
    payload = json.dumps({"type": msg.event_type, "data": msg.data, "timestamp": msg.timestamp})
    return f"event: {msg.event_type}\ndata: {payload}\n\n"


def sse_event_stream(q: queue.Queue[LiveEventMessage], timeout: float = 15.0) -> Iterator[str]:
    """SSE akış üreteci: veri geldikçe yield eder, boşlukta ping atar."""
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
    finally:
        hub.unsubscribe(q)
