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


def test_inline_comment_does_not_leak_into_embedding_provider() -> None:
    """`.env`'de `KEY=` satırının sonundaki yorum DEĞER sanılmamalı.

    Gerçek olay (Faz 2 sonrası denetim): `.env` şu satırı içeriyordu

        PD_EMBEDDING_PROVIDER=            # voyage | cohere | openai | local

    python-dotenv boş değerde satır sonu yorumunu ayıklamıyor; ayar
    "# voyage | cohere | openai | local" oluyordu. `make eval`, `make embed`
    ve `make cluster` bu yüzden çöküyordu.
    """
    assert Settings(embedding_provider="local   # yorum").embedding_provider == "local"
    assert Settings(embedding_provider="   ").embedding_provider == ""


def test_commented_out_provider_normalizes_to_unset() -> None:
    """`.env`'deki gerçek bozuk satırın tam metni.

    Kullanıcının kastı "boş bıraktım"dı; yorum ayıklanınca ayar boşa döner
    ve `build_backend` bilinen `hashing` yoluna uyarı logluyarak düşer.
    Eskiden değer yorumun kendisi oluyordu ve `PD_EMBEDDING_MODEL
    ayarlanmalı (provider=# voyage | ...)` diye anlamsız bir hata veriyordu.
    """
    broken = "# voyage | cohere | openai | local"
    assert Settings(embedding_provider=broken).embedding_provider == ""


def test_unknown_embedding_provider_is_rejected_at_startup() -> None:
    """Yazım hatası ilk embed çağrısında değil, açılışta patlamalı."""
    with pytest.raises(ValueError, match="Bilinmeyen embedding"):
        Settings(embedding_provider="voyaage")


def test_empty_provider_is_allowed_but_means_hashing() -> None:
    """Boş bırakmak geçerlidir (yerel geliştirme) — sessizce reddedilmez."""
    assert Settings(embedding_provider="").embedding_provider == ""


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
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert "git_sha" in body
    assert "env" in body


def test_health_ready_reports_dependencies() -> None:
    """Bağımlılıklar yoksa 503 döner ama uygulama çökmez."""
    from politikdesk.api.main import app

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code in (200, 503)
    body = response.json()
    assert set(body["checks"]) == {"postgres", "redis"}


def test_production_env_requires_api_token() -> None:
    """Üretim ortamında api_token zorunludur."""
    with pytest.raises(ValueError, match="PD_API_TOKEN zorunludur"):
        Settings(env="production", api_token="")

    # Belirteç varsa geçer
    s = Settings(env="production", api_token="secret_token_123")
    assert s.is_production
    assert s.api_token == "secret_token_123"

    # Geliştirme ortamında boş olabilir
    dev = Settings(env="development", api_token="")
    assert not dev.is_production
    assert dev.api_token == ""


def test_db_pool_min_max_ordering() -> None:
    """db_pool_min <= db_pool_max zorunludur."""
    with pytest.raises(ValueError, match="PD_DB_POOL_MIN"):
        Settings(db_pool_min=20, db_pool_max=10)

    s = Settings(db_pool_min=2, db_pool_max=15)
    assert s.db_pool_min == 2
    assert s.db_pool_max == 15


def test_empty_env_variables_fallback_to_defaults() -> None:
    """Boş .env şablonlarından gelen boş string değerleri varsayılana dönmeli."""
    s = Settings(
        log_format="",  # type: ignore[arg-type]
        llm_daily_budget_usd="",  # type: ignore[arg-type]
        embedding_dim="",  # type: ignore[arg-type]
        briefing_morning_hour="",  # type: ignore[arg-type]
        smtp_port="",  # type: ignore[arg-type]
        draft_max_chars="",  # type: ignore[arg-type]
    )
    assert s.log_format == "json"
    assert s.llm_daily_budget_usd == 5.0
    assert s.embedding_dim == 1024
    assert s.briefing_morning_hour == 8
    assert s.smtp_port == 587
    assert s.draft_max_chars == 600
