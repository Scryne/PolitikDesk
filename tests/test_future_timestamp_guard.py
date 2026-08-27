"""Regression Protection: Ingestion published_at timestamp clamping and future-date prevention."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from politikdesk.ingestion.models import RawItem
from politikdesk.ingestion.normalizer import normalize


def test_future_timestamp_is_clamped_to_now() -> None:
    """Yayım tarihi gelecekte olan makalelerin anlık zamana (now) sabitlendiğini doğrular."""
    now_ref = datetime(2026, 8, 25, 12, 0, 0, tzinfo=UTC)
    future_time = now_ref + timedelta(hours=3)

    raw = RawItem(
        source_slug="tcmb",
        url="https://www.tcmb.gov.tr/duyurular/future-doc.html",
        title="Gelecek Tarihli Duyuru",
        summary="Özet metin",
        published_at=future_time,
        lang="tr",
    )

    normalized = normalize(raw, now=now_ref)
    assert normalized.published_at is not None
    assert normalized.published_at <= now_ref
    assert normalized.published_at == now_ref


def test_past_timestamp_is_preserved() -> None:
    """Geçmiş tarihli makalelerin yayım tarihinin korunduğunu doğrular."""
    now_ref = datetime(2026, 8, 25, 12, 0, 0, tzinfo=UTC)
    past_time = now_ref - timedelta(hours=5)

    raw = RawItem(
        source_slug="tcmb",
        url="https://www.tcmb.gov.tr/duyurular/past-doc.html",
        title="Geçmiş Tarihli Duyuru",
        summary="Özet metin",
        published_at=past_time,
        lang="tr",
    )

    normalized = normalize(raw, now=now_ref)
    assert normalized.published_at == past_time
