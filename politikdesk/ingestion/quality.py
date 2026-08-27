"""Kaynak Kalite Skoru (Source Quality Score - SQS) Modeli (Faz 24).

PolitikDesk'e eklenen veya değerlendirilen kaynakların editoryal ve
teknik kalitesini 0–100 arasında deterministik olarak puanlar.

Metrikler:
1. Authority (A): Kurumsal otorite ve Tier seviyesi (0–100)
2. Reliability (R): Epistemik güvenilirlik ve teyit geçmişi (0–100)
3. Freshness (F): Güncellik ve yayın sıklığı (0–100)
4. Latency (L): Ağ yanıt süresi ve sunucu performansı (0–100)
5. Coverage (C): İçerik derinliği ve metin tamlığı (0–100)
6. Marginal Value (D): Tekillik ve bağımsız haber değeri (0–100)
7. Availability (V): Uptime ve teknik hata oranı (0–100)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceMetrics:
    authority: float  # 0 - 100 (Tier 1: 100, Tier 2: 85, Tier 3: 65, Social: 50)
    reliability: float  # 0 - 100 (Official: 100, Wire: 90, Verified News: 80)
    freshness: float  # 0 - 100
    latency_ms: float  # Milisaniye cinsinden yanıt süresi
    coverage: float  # 0 - 100 (Tam metin: 100, Özet: 75, Başlık: 40)
    marginal_value: float  # 0 - 100 (Özgün haber: 100, Ajans kopyası: 40)
    uptime_ratio: float  # 0.0 - 1.0 (99% = 0.99)


# Standart SQS Ağırlıkları (Toplam = 1.00)
WEIGHT_AUTHORITY = 0.25
WEIGHT_RELIABILITY = 0.25
WEIGHT_FRESHNESS = 0.15
WEIGHT_LATENCY = 0.10
WEIGHT_COVERAGE = 0.10
WEIGHT_MARGINAL_VALUE = 0.10
WEIGHT_AVAILABILITY = 0.05


def latency_to_score(latency_ms: float) -> float:
    """Gecikme süresini (ms) 0-100 puan aralığına normalize eder."""
    if latency_ms <= 0:
        return 0.0
    if latency_ms <= 200.0:
        return 100.0
    if latency_ms <= 500.0:
        return 100.0 - ((latency_ms - 200.0) / 300.0) * 20.0  # 100 -> 80
    if latency_ms <= 1000.0:
        return 80.0 - ((latency_ms - 500.0) / 500.0) * 20.0  # 80 -> 60
    if latency_ms <= 3000.0:
        return 60.0 - ((latency_ms - 1000.0) / 2000.0) * 30.0  # 60 -> 30
    return max(0.0, 30.0 - ((latency_ms - 3000.0) / 5000.0) * 30.0)


def calculate_sqs(metrics: SourceMetrics) -> float:
    """Source Quality Score (0 - 100) hesaplar."""
    l_score = latency_to_score(metrics.latency_ms)
    v_score = min(100.0, max(0.0, metrics.uptime_ratio * 100.0))

    sqs = (
        WEIGHT_AUTHORITY * metrics.authority
        + WEIGHT_RELIABILITY * metrics.reliability
        + WEIGHT_FRESHNESS * metrics.freshness
        + WEIGHT_LATENCY * l_score
        + WEIGHT_COVERAGE * metrics.coverage
        + WEIGHT_MARGINAL_VALUE * metrics.marginal_value
        + WEIGHT_AVAILABILITY * v_score
    )

    return round(min(100.0, max(0.0, sqs)), 2)
