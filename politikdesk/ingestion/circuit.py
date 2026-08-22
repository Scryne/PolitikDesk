"""Devre Kesici (Circuit Breaker) mekanizması (F5 / B-98).

Dış kaynaklar (RSS, Twitter/RSSHub, Resmî Gazete, TÜİK, TBMM, Sayıştay)
geçici veya kalıcı arızaya girdiğinde boru hattını bloke etmemek için
hızlı başarısızlık (fail-fast) ve otomatik kendini iyileştirme (self-healing)
sağlar.

Durumlar:
  - CLOSED (Kapalı): Normal çalışma. Tüm isteklere izin verilir.
  - OPEN (Açık): Hata eşiği aşıldı. Ağ isteği yapılmadan anında reddedilir.
  - HALF_OPEN (Yarım Açık): Soğuma süresi doldu. Tek bir test isteğine izin verilir.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from politikdesk.observability import get_logger

log = get_logger(__name__)


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Devre açık olduğu için istek engellendi (fail-fast)."""

    def __init__(self, host: str, retry_after_seconds: float, reason: str = "") -> None:
        self.host = host
        self.retry_after_seconds = retry_after_seconds
        self.reason = reason
        super().__init__(
            f"Devre açık ({host}): {reason or 'Kaynak geçici olarak devre dışı'}. "
            f"{int(retry_after_seconds)} sn sonra tekrar denenecek."
        )


@dataclass
class CircuitBreaker:
    """Tekil bir kaynak/host için thread-safe devre kesici."""

    host: str
    failure_threshold: int = 3
    recovery_timeout: float = 60.0
    half_open_max_probes: int = 1
    half_open_probe_timeout: float = 30.0

    _state: CircuitState = CircuitState.CLOSED
    _failure_count: int = 0
    _consecutive_success: int = 0
    _last_state_change: float = field(default_factory=time.monotonic)
    _last_error: str = ""
    _last_error_time: float = 0.0
    _active_probes: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._evaluate_state_locked()
            return self._state

    def _evaluate_state_locked(self) -> None:
        now = time.monotonic()
        if self._state == CircuitState.OPEN and (
            now - self._last_state_change >= self.recovery_timeout
        ):
            self._state = CircuitState.HALF_OPEN
            self._active_probes = 0
            self._last_state_change = now
            log.info("circuit_half_open_probe_allowed", host=self.host)
        elif self._state == CircuitState.HALF_OPEN and (
            now - self._last_state_change >= self.half_open_probe_timeout
        ):
            self._active_probes = 0
            self._last_state_change = now
            log.info("circuit_half_open_probe_timed_out_reset", host=self.host)

    def can_execute(self) -> bool:
        """İsteğin yürütülüp yürütülemeyeceğini döner."""
        with self._lock:
            self._evaluate_state_locked()
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.HALF_OPEN:
                if self._active_probes < self.half_open_max_probes:
                    self._active_probes += 1
                    return True
                return False
            return False

    def check_or_raise(self) -> None:
        """Devre açıksa CircuitOpenError fırlatır."""
        with self._lock:
            self._evaluate_state_locked()
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._last_state_change
                remaining = max(0.0, self.recovery_timeout - elapsed)
                raise CircuitOpenError(
                    host=self.host,
                    retry_after_seconds=remaining,
                    reason=self._last_error,
                )
            if self._state == CircuitState.HALF_OPEN:
                if self._active_probes >= self.half_open_max_probes:
                    raise CircuitOpenError(
                        host=self.host,
                        retry_after_seconds=5.0,
                        reason="Yarım-açık probe isteği devam ediyor",
                    )
                self._active_probes += 1

    def record_success(self) -> None:
        """Başarılı isteği kaydeder."""
        with self._lock:
            now = time.monotonic()
            if self._state == CircuitState.HALF_OPEN:
                self._consecutive_success += 1
                if self._consecutive_success >= self.half_open_max_probes:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._consecutive_success = 0
                    self._active_probes = 0
                    self._last_state_change = now
                    log.info("circuit_closed_recovered", host=self.host)
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def record_failure(self, error: str = "") -> None:
        """Başarısız isteği kaydeder."""
        with self._lock:
            now = time.monotonic()
            self._failure_count += 1
            self._last_error = error
            self._last_error_time = now
            self._consecutive_success = 0

            tripped = (
                self._state == CircuitState.HALF_OPEN
                or self._failure_count >= self.failure_threshold
            )
            if self._state in (CircuitState.CLOSED, CircuitState.HALF_OPEN) and tripped:
                self._state = CircuitState.OPEN
                self._active_probes = 0
                self._last_state_change = now
                log.warning(
                    "circuit_tripped_open",
                    host=self.host,
                    failures=self._failure_count,
                    error=error,
                    cooldown=self.recovery_timeout,
                )

    def reset(self) -> None:
        """Devreyi sıfırlar (testler için)."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._consecutive_success = 0
            self._active_probes = 0
            self._last_state_change = time.monotonic()
            self._last_error = ""
            self._last_error_time = 0.0

    def get_metrics(self) -> dict[str, Any]:
        """Sağlık panosu için anlık metrikler."""
        with self._lock:
            self._evaluate_state_locked()
            now = time.monotonic()
            return {
                "host": self.host,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "last_error": self._last_error,
                "seconds_in_state": round(now - self._last_state_change, 1),
                "is_healthy": self._state == CircuitState.CLOSED,
            }


class SourceCircuitRegistry:
    """Tüm kaynakların devre kesicilerini yöneten merkezi kayıt defteri."""

    def __init__(self) -> None:
        self._circuits: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get(self, host: str, **kwargs: Any) -> CircuitBreaker:
        normalized_host = host.lower().strip()
        with self._lock:
            if normalized_host not in self._circuits:
                self._circuits[normalized_host] = CircuitBreaker(host=normalized_host, **kwargs)
            return self._circuits[normalized_host]

    def all_metrics(self) -> list[dict[str, Any]]:
        with self._lock:
            return [cb.get_metrics() for cb in self._circuits.values()]

    def reset_all(self) -> None:
        with self._lock:
            for cb in self._circuits.values():
                cb.reset()


_GLOBAL_REGISTRY = SourceCircuitRegistry()


def get_circuit(host: str, **kwargs: Any) -> CircuitBreaker:
    return _GLOBAL_REGISTRY.get(host, **kwargs)


def get_all_circuit_metrics() -> list[dict[str, Any]]:
    return _GLOBAL_REGISTRY.all_metrics()


def reset_all_circuits() -> None:
    _GLOBAL_REGISTRY.reset_all()
