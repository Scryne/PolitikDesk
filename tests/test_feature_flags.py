"""Özellik Bayrakları (Feature Flags & Rollback Toggles) Testleri."""

from __future__ import annotations

from politikdesk.feature_flags import (
    is_live_notifications_enabled,
    is_reranker_enabled,
    is_social_publish_enabled,
    is_twitter_ingestion_enabled,
)


def test_default_feature_flags_state() -> None:
    """Varsayılan ortamda veri çekme ve analiz bayrakları açık, otomatik yayınlama ise güvenlik için kapalı olmalıdır."""
    assert is_twitter_ingestion_enabled() is True
    assert is_live_notifications_enabled() is True
    assert is_reranker_enabled() is True
    assert is_social_publish_enabled() is False


def test_feature_flags_toggle_with_env_vars(monkeypatch: object) -> None:
    """Ortam değişkenleri ile bayrakların açılıp kapatılabilmesi doğrulanmalı."""
    from _pytest.monkeypatch import MonkeyPatch

    mp = monkeypatch if isinstance(monkeypatch, MonkeyPatch) else MonkeyPatch()
    mp.setenv("PD_TWITTER_INGESTION_ENABLED", "false")
    mp.setenv("PD_LIVE_NOTIFICATIONS_ENABLED", "0")
    mp.setenv("PD_RERANKER_ENABLED", "no")
    mp.setenv("PD_SOCIAL_PUBLISH_ENABLED", "true")

    assert is_twitter_ingestion_enabled() is False
    assert is_live_notifications_enabled() is False
    assert is_reranker_enabled() is False
    assert is_social_publish_enabled() is True
