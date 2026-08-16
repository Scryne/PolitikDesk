"""B-69 ve B-52 regresyon ve doğruluk testleri (AŞAMA 9 · Madde 11).

B-69: Metrik seçim doğruluğu ve izin verilen metrik sözlüğü (VALID_METRICS).
B-52: numeric_guard yanlış-pozitif oranı — farklı dönem/birim/metrik çiftlerinin
      hatalı çelişki üretmediğinin doğrulanması.
"""

from __future__ import annotations

import pytest

from politikdesk.evidence.independence import EvidenceArticle
from politikdesk.evidence.rules import Claim, Evidence, compute_status
from politikdesk.nlp.claims import (
    VALID_METRICS,
    validate_claim,
)


# ===========================================================================
# B-69 — Metrik Seçim Doğruluğu ve İzin Verilen Sözlük Denetimi
# ===========================================================================
@pytest.mark.parametrize(
    ("metric_name", "is_valid"),
    [
        ("gdp_growth_annual", True),
        ("gdp_growth_quarterly", True),
        ("tufe_annual", True),
        ("tufe_monthly", True),
        ("policy_rate", True),
        ("unemployment_rate", True),
        ("reserves", True),
        ("budget_balance", True),
        ("current_account_balance", True),
        ("other", True),
        ("uydurma_metrik", False),
        ("random_indicator", False),
        ("inflation_rate_invalid", False),
    ],
)
def test_b69_metric_dictionary_validation(metric_name: str, is_valid: bool) -> None:
    """İddia çıkarımında metrik adının VALID_METRICS sözlüğünde olup olmadığını test eder."""
    assert (metric_name in VALID_METRICS) == is_valid
    raw = {
        "claim_text": "Ekonomi göstergesi açıklandı.",
        "claim_type": "number",
        "quote_span": "Ekonomi göstergesi açıklandı.",
        "normalized_value": {
            "metric": metric_name,
            "value": 10.5,
            "period": "2026-07",
            "unit": "percent",
        },
    }
    res = validate_claim(raw, "Ekonomi göstergesi açıklandı.")
    if is_valid:
        assert res.is_valid, f"{metric_name} geçerli bir metrik olmalıdır, sorunlar: {res.problems}"
    else:
        assert not res.is_valid, f"{metric_name} geçersiz bir metrik olduğundan reddedilmelidir."
        assert any("gecersiz metric" in p for p in res.problems)


def test_b69_ar_ge_spending_classified_as_other() -> None:
    """Canlı koşumda reserves olarak yanlış kodlanan Ar-Ge harcamasının 'other' olarak doğrulanması."""
    raw = {
        "claim_text": "TÜBİTAK Ar-Ge desteği 12 milyar TL oldu.",
        "claim_type": "number",
        "quote_span": "TÜBİTAK Ar-Ge desteği 12 milyar TL oldu.",
        "normalized_value": {
            "metric": "other",
            "value": 12.0,
            "period": "2026",
            "unit": "TRY_billion",
        },
    }
    res = validate_claim(raw, "TÜBİTAK Ar-Ge desteği 12 milyar TL oldu.")
    assert res.is_valid
    assert res.normalized_value is not None
    assert res.normalized_value.get("metric") == "other"


# ===========================================================================
# B-52 — Numeric Guard Yanlış Pozitif (False Contradiction) Koruması
# ===========================================================================
def test_b52_different_periods_do_not_contradict() -> None:
    """Farklı dönemlere (örn. 2026-Q1 vs 2026-Q2) ait farklı değerler çelişki sayılmamalıdır."""
    claim = Claim(
        claim_id=1,
        claim_text="2026 ilk çeyrek büyümesi yüzde 4,2 oldu.",
        claim_type="number",
        normalized_value={
            "metric": "gdp_growth_quarterly",
            "value": 4.2,
            "period": "2026-Q1",
            "unit": "percent",
        },
    )
    ev1 = Evidence(
        article=EvidenceArticle(
            article_id=101,
            source_slug="reuters",
            tier=2,
            kind="wire",
            independence_group="reuters",
            text="2025 son çeyrek büyümesi yüzde 3,8 olarak gerçekleşmişti.",
        ),
        stance="neutral",
    )
    result = compute_status(claim, [ev1])
    assert result.status != "contradicted"


def test_b52_different_metrics_do_not_contradict() -> None:
    """Farklı metriklere (örn. manşet enflasyon vs çekirdek enflasyon) ait değerler çelişki sayılmamalıdır."""
    claim = Claim(
        claim_id=2,
        claim_text="TÜFE yıllık yüzde 28,4 olarak açıklandı.",
        claim_type="number",
        normalized_value={
            "metric": "tufe_annual",
            "value": 28.4,
            "period": "2026-07",
            "unit": "percent",
        },
    )
    ev_core = Evidence(
        article=EvidenceArticle(
            article_id=102,
            source_slug="bloomberght",
            tier=3,
            kind="media",
            independence_group="ciner",
            text="Özel kapsamlı TÜFE (C endeksi / çekirdek) yıllık yüzde 24,1 arttı.",
        ),
        stance="neutral",
    )
    result = compute_status(claim, [ev_core])
    assert result.status != "contradicted"


def test_b52_same_metric_and_period_different_value_contradicts() -> None:
    """Aynı metrik, aynı dönem ve aynı birimde taban tabana zıt değerler R1 ile çelişki (contradicted) üretmelidir."""
    claim = Claim(
        claim_id=3,
        claim_text="Temmuz işsizlik oranı yüzde 8,8 oldu.",
        claim_type="number",
        normalized_value={
            "metric": "unemployment_rate",
            "value": 8.8,
            "period": "2026-07",
            "unit": "percent",
        },
    )
    ev_support = Evidence(
        article=EvidenceArticle(
            article_id=103,
            source_slug="tuik",
            tier=1,
            kind="official",
            independence_group="tuik",
            text="Temmuz işsizlik oranı yüzde 8,8 olarak açıklandı.",
        ),
        stance="supports",
    )
    ev_conflict = Evidence(
        article=EvidenceArticle(
            article_id=104,
            source_slug="reuters",
            tier=2,
            kind="wire",
            independence_group="reuters",
            text="Temmuz işsizlik oranı yüzde 10,2 olarak açıklandı.",
        ),
        stance="contradicts",
    )
    result = compute_status(claim, [ev_support, ev_conflict])
    assert result.status == "contradicted"
    assert result.rule == "R1"
