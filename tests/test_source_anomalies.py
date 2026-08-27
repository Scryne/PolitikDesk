"""Kaynak anomali ve verim izleme testleri (Faz F)."""

from datetime import UTC, datetime, timedelta

from politikdesk.ingestion.source_anomalies import (
    classify_duplicate_spike,
    classify_empty_feed,
)


def test_empty_feed_anomaly_high_volume_silence() -> None:
    """Normalde günde 50 haber üreten kaynak 0 haber verdiğinde EMPTY_ANOMALY dönmelidir."""
    report = classify_empty_feed(
        slug="aa-ekonomi",
        adapter="rss",
        items_in_window=0,
        historical_daily_mean=50.0,
        last_item_at=datetime.now(UTC) - timedelta(hours=3),
    )
    assert report.status == "EMPTY_ANOMALY"
    assert "sıfır öğe" in report.detail


def test_empty_feed_low_frequency_official_source_normal() -> None:
    """Seyrek yayın yapan resmi kurum (Sayıştay/Resmi Gazete) 0 haber verdiğinde EMPTY_EXPECTED dönmelidir."""
    report = classify_empty_feed(
        slug="sayistay",
        adapter="sayistay",
        items_in_window=0,
        historical_daily_mean=0.5,
        last_item_at=datetime.now(UTC) - timedelta(hours=24),
    )
    assert report.status == "EMPTY_EXPECTED"


def test_empty_feed_stale_detection() -> None:
    """Beklenen bütçenin 2 katından uzun süre veri gelmeyen kaynak STALE dönmelidir."""
    report = classify_empty_feed(
        slug="dunya",
        adapter="rss",
        items_in_window=0,
        historical_daily_mean=20.0,
        last_item_at=datetime.now(UTC) - timedelta(hours=15),  # RSS budget is 6h -> 15h > 12h
    )
    assert report.status == "STALE"


def test_empty_feed_low_yield_anomaly() -> None:
    """Günde 100 haber üreten kaynaktan sadece 2 haber geldiğinde LOW_YIELD_ANOMALY dönmelidir."""
    report = classify_empty_feed(
        slug="hurriyet",
        adapter="rss",
        items_in_window=2,
        historical_daily_mean=100.0,
        last_item_at=datetime.now(UTC) - timedelta(hours=1),
    )
    assert report.status == "LOW_YIELD_ANOMALY"


def test_duplicate_spike_anomalous_volume() -> None:
    """100 öğeden 90'ı tekrar ise ANOMALOUS olarak işaretlenmelidir."""
    report = classify_duplicate_spike(
        slug="cnnturk",
        adapter="rss",
        fetched_count=100,
        accepted_count=10,
        duplicate_count=90,
    )
    assert report.status == "ANOMALOUS"
    assert report.duplicate_ratio == 0.9


def test_duplicate_spike_series_adapter_exemption() -> None:
    """EVDS veya TÜİK SDMX seri adaptörlerinde %95 tekrar olsa dahi NORMAL kabul edilmelidir."""
    report = classify_duplicate_spike(
        slug="tcmb-evds",
        adapter="evds",
        fetched_count=100,
        accepted_count=5,
        duplicate_count=95,
    )
    assert report.status == "NORMAL"
    assert "seri adaptörü" in report.detail.lower()


def test_duplicate_spike_insufficient_baseline() -> None:
    """5'ten az öğe çekildiğinde UNKNOWN_BASELINE dönmelidir."""
    report = classify_duplicate_spike(
        slug="betam",
        adapter="rss",
        fetched_count=2,
        accepted_count=1,
        duplicate_count=1,
    )
    assert report.status == "UNKNOWN_BASELINE"
