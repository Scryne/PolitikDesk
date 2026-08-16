"""PolitikDesk — Dinamik Özellik Bayrakları ve Geri Alma (Rollback) Yönetimi.

Tüm yeni bileşenler (Twitter adaptörü, canlı bildirimler, reranker, X yayınlayıcı)
ortam değişkenleri veya çalışma zamanı ayarları ile anında devre dışı bırakılabilir.
"""

from __future__ import annotations

import os


def _bool_env(key: str, default: bool = True) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on", "enabled")


def is_twitter_ingestion_enabled() -> bool:
    """X / Twitter hesaplarının veri boru hattında taranmasını kontrol eder."""
    return _bool_env("PD_TWITTER_INGESTION_ENABLED", default=True)


def is_live_notifications_enabled() -> bool:
    """SSE tabanlı editoryal anlık bildirim akışını kontrol eder."""
    return _bool_env("PD_LIVE_NOTIFICATIONS_ENABLED", default=True)


def is_reranker_enabled() -> bool:
    """Türkçe siyaset ve yasama reranker katmanını kontrol eder."""
    return _bool_env("PD_RERANKER_ENABLED", default=True)


def is_social_publish_enabled() -> bool:
    """Editoryal taslakların X'e yayınlanmasını kontrol eder (varsayılan: False)."""
    return _bool_env("PD_SOCIAL_PUBLISH_ENABLED", default=False)
