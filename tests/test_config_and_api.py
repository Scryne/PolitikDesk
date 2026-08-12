"""Ayarlar ve API iskeleti testleri (F0-12, F0-18)."""

from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from politikdesk import __version__
from politikdesk.config import Settings
from politikdesk.observability import configure_logging, get_logger


def test_embedding_dim_locked_to_schema() -> None:
    """Şema VECTOR(1024) — ayar bununla çelişemez."""
    with pytest.raises(ValueError, match="1024"):
        Settings(embedding_dim=768)


def test_cluster_thresholds_must_be_ordered() -> None:
    """Spec §11.4: T_LOW < T_HIGH."""
    with pytest.raises(ValueError, match="cluster_t_low"):
        Settings(cluster_t_high=0.70, cluster_t_low=0.90)


def test_defaults_match_calibrated_thresholds() -> None:
    """D20 — F2-14'te kalibre edilmiş eşikler (`eval/threshold_report.md`).

    Spec §11.4'ün tahminleri 0,86 / 0,78 idi; Golden Set üzerinde bu
    değerler false merge oranını %10,7 veriyordu ve G2'nin pazarlıksız
    koşulu (≤ %5) tutmuyordu. 0,92 / 0,88 ile oran %2,6'ya iniyor.

    Bu test bir "sabit doğrulama"dan fazlasıdır: eşikleri sessizce
    değiştiren bir commit, kalibrasyon raporunu güncellemeye zorlanır.
    """
    s = Settings()
    assert s.cluster_t_high == 0.92
    assert s.cluster_t_low == 0.88


def test_threshold_ordering_is_enforced() -> None:
    """T_LOW < T_HIGH — denetim bandı ters çevrilemez."""
    with pytest.raises(ValueError, match="t_low"):
        Settings(cluster_t_high=0.80, cluster_t_low=0.90)


def test_logs_are_json_formatted(capsys: pytest.CaptureFixture[str]) -> None:
    """F0-18 DoD: log JSON formatında."""
    configure_logging(Settings(log_format="json", log_level="INFO"))
    logging.getLogger().handlers[0].setLevel(logging.INFO)

    get_logger("test").info("olay_kaydi", kaynak="tuik", sayi=3)
    captured = capsys.readouterr().out.strip().splitlines()

    assert captured, "Log çıktısı yok"
    payload = json.loads(captured[-1])
    assert payload["event"] == "olay_kaydi"
    assert payload["kaynak"] == "tuik"
    assert payload["level"] == "info"
    assert "timestamp" in payload

    configure_logging(Settings(log_format="console"))  # diğer testleri etkilemesin


def test_health_live_endpoint() -> None:
    from politikdesk.api.main import app

    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_health_ready_reports_dependencies() -> None:
    """Bağımlılıklar yoksa 503 döner ama uygulama çökmez."""
    from politikdesk.api.main import app

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code in (200, 503)
    body = response.json()
    assert set(body["checks"]) == {"postgres", "redis"}
