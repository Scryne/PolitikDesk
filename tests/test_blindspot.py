from __future__ import annotations

from politikdesk.evidence.blindspot import analyze_blindspot


def test_blindspot_single_source():
    report = analyze_blindspot(
        event_id=101,
        covered_sources=["t24"],
        all_registered_sources=["tcmb", "tuik", "aa", "bloomberght", "t24", "diken"],
    )
    assert report.event_id == 101
    assert report.covered_count == 1
    assert report.total_sources_count == 6
    assert report.severity == "single_source"
    assert "t24" in report.covered_sources
    assert "tcmb" in report.missing_sources
    d = report.to_dict()
    assert d["severity"] == "single_source"
    assert d["covered_count"] == 1


def test_blindspot_independent_only():
    report = analyze_blindspot(
        event_id=102,
        covered_sources=["t24", "diken", "sozcu"],
        all_registered_sources=["tcmb", "tuik", "aa", "bloomberght", "t24", "diken", "sozcu"],
    )
    assert report.severity == "independent_only"
    assert report.tier_breakdown.tier3_independent == 3
    assert report.tier_breakdown.tier1_official == 0
    assert report.tier_breakdown.tier2_mainstream == 0
    assert "Kör Noktası" in report.summary_label


def test_blindspot_mainstream_only():
    report = analyze_blindspot(
        event_id=103,
        covered_sources=["aa", "trt_haber", "bloomberght"],
        all_registered_sources=["tcmb", "tuik", "aa", "trt_haber", "bloomberght", "t24", "diken"],
    )
    assert report.severity == "mainstream_only"
    assert report.tier_breakdown.tier2_mainstream == 3
    assert report.tier_breakdown.tier3_independent == 0
    assert "Ana Akım" in report.summary_label


def test_blindspot_balanced():
    report = analyze_blindspot(
        event_id=104,
        covered_sources=["tcmb", "aa", "bloomberght", "t24"],
        all_registered_sources=["tcmb", "tuik", "aa", "bloomberght", "t24", "diken"],
    )
    assert report.severity == "balanced"
    assert report.tier_breakdown.tier1_official == 1
    assert report.tier_breakdown.tier2_mainstream == 2
    assert report.tier_breakdown.tier3_independent == 1
    assert report.coverage_ratio > 0.5
    assert "Dengeli" in report.summary_label


def test_blindspot_custom_tiers():
    custom_tiers = {"kaynak_a": 1, "kaynak_b": 3}
    report = analyze_blindspot(
        event_id=105,
        covered_sources=["kaynak_a", "kaynak_b"],
        all_registered_sources=["kaynak_a", "kaynak_b", "kaynak_c"],
        source_tiers=custom_tiers,
    )
    assert report.tier_breakdown.tier1_official == 1
    assert report.tier_breakdown.tier3_independent == 1
    assert report.severity == "balanced"
