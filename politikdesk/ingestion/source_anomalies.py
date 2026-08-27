"""Kaynak anomali ve verim izleme modülü (Faz F İyileştirmesi).

Kaynakların teknik olarak ayakta (HTTP 200) olmasına rağmen içeriksel olarak
bozulduğu (boş akış, aşırı tekrar patlaması) durumları tespit eder.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal

from politikdesk.observability import get_logger

log = get_logger(__name__)

EmptyFeedStatus = Literal[
    "HEALTHY",
    "LOW_YIELD_EXPECTED",
    "LOW_YIELD_ANOMALY",
    "EMPTY_EXPECTED",
    "EMPTY_ANOMALY",
    "STALE",
    "UNKNOWN",
]

DuplicateSpikeStatus = Literal[
    "NORMAL",
    "ELEVATED",
    "ANOMALOUS",
    "UNKNOWN_BASELINE",
]

# Adaptör türüne göre beklenen normal sessizlik bütçesi (saat)
EXPECTED_CADENCE_HOURS: Final[dict[str, float]] = {
    "rss": 6.0,
    "twitter": 24.0,
    "tuik_sdmx": 24.0,
    "evds": 24.0,
    "resmi_gazete": 48.0,
    "sayistay": 168.0,
    "tbmm": 72.0,
    "cumhurbaskanligi": 72.0,
    "wp_rest": 48.0,
    "generic_html": 48.0,
}
DEFAULT_CADENCE_HOURS: Final[float] = 12.0

SERIES_ADAPTERS: Final[frozenset[str]] = frozenset({"evds", "tuik_sdmx"})


@dataclass(frozen=True)
class YieldAnomalyReport:
    """Bir kaynağın verim ve boş akış anomali durumu."""

    slug: str
    adapter: str
    status: EmptyFeedStatus
    items_recent: int
    expected_cadence_hours: float
    hours_since_last_item: float | None
    detail: str


@dataclass(frozen=True)
class DuplicateSpikeReport:
    """Bir kaynağın tekrar hacmi anomali durumu."""

    slug: str
    adapter: str
    status: DuplicateSpikeStatus
    fetched_count: int
    accepted_count: int
    duplicate_count: int
    duplicate_ratio: float
    detail: str


def classify_empty_feed(
    slug: str,
    adapter: str,
    *,
    items_in_window: int,
    historical_daily_mean: float | None = None,
    last_item_at: datetime | None = None,
    now: datetime | None = None,
) -> YieldAnomalyReport:
    """Bir kaynağın boş akış veya düşük verim durumunu belirler."""
    current_time = now or datetime.now(UTC)
    cadence = EXPECTED_CADENCE_HOURS.get(adapter.lower(), DEFAULT_CADENCE_HOURS)
    
    hours_since = (
        (current_time - last_item_at).total_seconds() / 3600.0
        if last_item_at
        else None
    )

    # 1. Hiç geçmiş veri yoksa
    if historical_daily_mean is None and hours_since is None and items_in_window == 0:
        return YieldAnomalyReport(
            slug=slug,
            adapter=adapter,
            status="UNKNOWN",
            items_recent=0,
            expected_cadence_hours=cadence,
            hours_since_last_item=None,
            detail="Yeterli geçmiş veri yok, henüz ölçülemedi.",
        )

    # 2. Akışta son pencerede öğe varsa
    if items_in_window > 0:
        if (
            historical_daily_mean
            and historical_daily_mean >= 10.0
            and items_in_window < (historical_daily_mean * 0.1)
        ):
            return YieldAnomalyReport(
                slug=slug,
                adapter=adapter,
                status="LOW_YIELD_ANOMALY",
                items_recent=items_in_window,
                expected_cadence_hours=cadence,
                hours_since_last_item=hours_since,
                detail=(
                    f"Beklenen günlük ortalama {historical_daily_mean:.1f} iken "
                    f"yalnızca {items_in_window} öğe geldi."
                ),
            )
        return YieldAnomalyReport(
            slug=slug,
            adapter=adapter,
            status="HEALTHY",
            items_recent=items_in_window,
            expected_cadence_hours=cadence,
            hours_since_last_item=hours_since,
            detail=f"Normal akış: {items_in_window} öğe işlendi.",
        )

    # 3. Akışta 0 öğe varsa
    if hours_since is not None and hours_since > (cadence * 2.0):
        return YieldAnomalyReport(
            slug=slug,
            adapter=adapter,
            status="STALE",
            items_recent=0,
            expected_cadence_hours=cadence,
            hours_since_last_item=hours_since,
            detail=f"{hours_since:.1f} saattir veri gelmedi (bütçe: {cadence:.0f} saat).",
        )

    # Normalde yüksek hacimli bir haber kaynağı (örn: günlük > 10 haber) aniden 0 veriyorsa
    if historical_daily_mean and historical_daily_mean >= 10.0:
        return YieldAnomalyReport(
            slug=slug,
            adapter=adapter,
            status="EMPTY_ANOMALY",
            items_recent=0,
            expected_cadence_hours=cadence,
            hours_since_last_item=hours_since,
            detail=(
                f"Yüksek hacimli kaynak ({historical_daily_mean:.1f} haber/gün) "
                f"sıfır öğe üretti."
            ),
        )

    # Doğal olarak seyrek kaynaklar (Sayıştay, Resmi Gazete, BETAM)
    return YieldAnomalyReport(
        slug=slug,
        adapter=adapter,
        status="EMPTY_EXPECTED",
        items_recent=0,
        expected_cadence_hours=cadence,
        hours_since_last_item=hours_since,
        detail="Seyrek yayın yapan kaynak bütçe dahilinde sessiz.",
    )


def classify_duplicate_spike(
    slug: str,
    adapter: str,
    *,
    fetched_count: int,
    accepted_count: int,
    duplicate_count: int,
) -> DuplicateSpikeReport:
    """Bir kaynaktaki tekrar patlaması durumunu tespit eder."""
    if fetched_count < 5:
        ratio = (duplicate_count / fetched_count) if fetched_count > 0 else 0.0
        return DuplicateSpikeReport(
            slug=slug,
            adapter=adapter,
            status="UNKNOWN_BASELINE",
            fetched_count=fetched_count,
            accepted_count=accepted_count,
            duplicate_count=duplicate_count,
            duplicate_ratio=round(ratio, 3),
            detail="Yetersiz öğe sayısı (< 5) ile değerlendirilemedi.",
        )

    ratio = duplicate_count / fetched_count

    # Seri adaptörleri (EVDS, TÜİK SDMX) her turda tüm seriyi yeniden çeker
    if adapter.lower() in SERIES_ADAPTERS:
        return DuplicateSpikeReport(
            slug=slug,
            adapter=adapter,
            status="NORMAL",
            fetched_count=fetched_count,
            accepted_count=accepted_count,
            duplicate_count=duplicate_count,
            duplicate_ratio=round(ratio, 3),
            detail="Seri adaptörü: periyodik veri tekrarı beklenen davranış.",
        )

    if ratio >= 0.85 and fetched_count >= 20:
        return DuplicateSpikeReport(
            slug=slug,
            adapter=adapter,
            status="ANOMALOUS",
            fetched_count=fetched_count,
            accepted_count=accepted_count,
            duplicate_count=duplicate_count,
            duplicate_ratio=round(ratio, 3),
            detail=(
                f"Aşırı tekrar oranı: %{ratio*100:.1f} "
                f"({duplicate_count}/{fetched_count} öğe tekrar)."
            ),
        )

    if ratio >= 0.50:
        return DuplicateSpikeReport(
            slug=slug,
            adapter=adapter,
            status="ELEVATED",
            fetched_count=fetched_count,
            accepted_count=accepted_count,
            duplicate_count=duplicate_count,
            duplicate_ratio=round(ratio, 3),
            detail=f"Yüksek tekrar oranı: %{ratio*100:.1f}.",
        )

    return DuplicateSpikeReport(
        slug=slug,
        adapter=adapter,
        status="NORMAL",
        fetched_count=fetched_count,
        accepted_count=accepted_count,
        duplicate_count=duplicate_count,
        duplicate_ratio=round(ratio, 3),
        detail="Tekrar oranı normal sınırlar içinde.",
    )
