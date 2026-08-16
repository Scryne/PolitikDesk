"""B-81 Capraz Kaynak Iddia Eslestirici Testleri."""

from __future__ import annotations

import pytest

from politikdesk.nlp.claims import ExtractedClaim
from politikdesk.nlp.cross_source_matcher import (
    are_claims_equivalent,
    jaccard_similarity,
    match_and_group_claims,
)


def test_jaccard_similarity_basic() -> None:
    set_a = {"tcmb", "faiz", "karar"}
    set_b = {"tcmb", "faiz", "oran"}
    assert jaccard_similarity(set_a, set_b) == pytest.approx(2 / 4)


def test_number_claims_match_exact_normalized_values() -> None:
    c1 = ExtractedClaim(
        claim_text="TUFE aylik yuzde 1,78 artti.",
        claim_type="number",
        quote_span="aylik %1,78 artti",
        normalized_value={
            "metric": "tufe_monthly",
            "value": 1.78,
            "unit": "%",
            "period": "2026-07",
        },
    )
    c2 = ExtractedClaim(
        claim_text="Tuketici enflasyonu temmuzda yuzde 1,78 olarak gerceklesti.",
        claim_type="number",
        quote_span="yuzde 1,78 olarak gerceklesti",
        normalized_value={
            "metric": "tufe_monthly",
            "value": 1.78,
            "unit": "%",
            "period": "2026-07",
        },
    )
    assert are_claims_equivalent(c1, c2) is True


def test_number_claims_do_not_match_different_metrics() -> None:
    c1 = ExtractedClaim(
        claim_text="TUFE aylik yuzde 1,78 artti.",
        claim_type="number",
        quote_span="aylik %1,78 artti",
        normalized_value={
            "metric": "tufe_monthly",
            "value": 1.78,
            "unit": "%",
            "period": "2026-07",
        },
    )
    c2 = ExtractedClaim(
        claim_text="YI-UFE aylik yuzde 1,78 artti.",
        claim_type="number",
        quote_span="aylik %1,78 artti",
        normalized_value={"metric": "ufe_monthly", "value": 1.78, "unit": "%", "period": "2026-07"},
    )
    assert are_claims_equivalent(c1, c2) is False


def test_fact_claims_match_with_semantic_variation() -> None:
    c1 = ExtractedClaim(
        claim_text="TCMB Para Politikasi Kurulu politika faizini yuzde 37 sabit tuttu.",
        claim_type="fact",
        quote_span="faizi yuzde 37 sabit tuttu",
    )
    c2 = ExtractedClaim(
        claim_text="Merkez Bankasi Para Politikasi Kurulu faiz oranini yuzde 37 seviyesinde sabit birakti.",
        claim_type="fact",
        quote_span="faiz oranini yuzde 37 seviyesinde sabit birakti",
    )
    assert are_claims_equivalent(c1, c2) is True


def test_fact_claims_do_not_match_on_negation_conflict() -> None:
    c1 = ExtractedClaim(
        claim_text="Sanayi uretimi ilk ceyrekte artti.",
        claim_type="fact",
        quote_span="sanayi uretimi artti",
    )
    c2 = ExtractedClaim(
        claim_text="Sanayi uretimi ilk ceyrekte artmadi, geriledi.",
        claim_type="fact",
        quote_span="sanayi uretimi artmadi",
    )
    assert are_claims_equivalent(c1, c2) is False


def test_match_and_group_claims_aggregates_sources() -> None:
    c1 = ExtractedClaim(
        claim_text="TCMB politika faizini yuzde 37 sabit tuttu.",
        claim_type="fact",
        quote_span="TCMB faizi %37 tuttu",
    )
    c2 = ExtractedClaim(
        claim_text="Merkez Bankasi politika faizini yuzde 37 seviyesinde sabit birakti.",
        claim_type="fact",
        quote_span="faizi yuzde 37 seviyesinde sabit birakti",
    )
    c3 = ExtractedClaim(
        claim_text="Moodys Turkiye kredi notunu artirdi.",
        claim_type="fact",
        quote_span="kredi notunu artirdi",
    )

    collected = [(c1, 101), (c2, 102), (c3, 103)]
    grouped = match_and_group_claims(collected)

    assert len(grouped) == 2
    rep1, sources1 = grouped[0]
    assert len(sources1) == 2
    assert {s[0] for s in sources1} == {101, 102}

    rep2, sources2 = grouped[1]
    assert len(sources2) == 1
    assert sources2[0][0] == 103
