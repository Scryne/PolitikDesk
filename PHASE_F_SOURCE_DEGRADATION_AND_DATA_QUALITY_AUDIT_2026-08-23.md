# POLITIKDESK — PHASE F SOURCE DEGRADATION & DATA QUALITY AUDIT
**Date:** 2026-08-23  
**Auditor:** Information Integrity Researcher & Data Quality Auditor  
**Status:** DRIFT & DEGRADATION AUDIT COMPLETE  

---

## 1. Executive Summary

A source may remain technically reachable (returning HTTP 200 with valid XML) while becoming informationally or epistemically degraded. This audit evaluates the detectability of 6 real-world data quality drift scenarios.

---

## 2. Source Degradation Scenario Assessment

| Scenario | Degradation Mode Description | Pipeline Detection Mechanism | Detectability Classification | Audit Notes & Operational Boundary |
| :--- | :--- | :--- | :---: | :--- |
| **Scenario A** | Valid RSS but articles unrelated to configured topic (e.g. sports/tabloid drift). | Downstream Vertical Topic Keyword Filters (`politikdesk.verticals`). | **`PARTIALLY_DETECTED`** | Unrelated articles rejected at vertical filter; however, source-level alert is not triggered until yield drops below threshold. |
| **Scenario B** | Valid feed replaying the same 3 articles continuously. | `classify_duplicate_spike` in `source_anomalies.py` flags $\ge 85\%$ duplicate ratio. | **`DETECTED`** | Flagged as `ANOMALOUS` duplicate volume spike. |
| **Scenario C** | Sudden 90% syndication increase (source ceases original reporting). | `source_quality.py` rolling yield drops; `independence.py` collapses all into `wire:<slug>`. | **`DETECTED`** | `yield_consistency` metric drops; no artificial corroboration inflation. |
| **Scenario D** | Article body length drops dramatically ($< 50$ characters). | Min-length filter in `RawItem` normalization (`len(body) < 100`). | **`DETECTED`** | Short/truncated bodies discarded or flagged as stub. |
| **Scenario E** | Publication timestamps freeze / become stale. | `classify_empty_feed` in `source_anomalies.py` tracks `hours_since_last_item`. | **`DETECTED`** | Flagged as `STALE` when silence exceeds $2\times$ cadence budget. |
| **Scenario F** | High volume of articles with near-zero marginal intelligence (e.g. clickbait). | LLM Claim Extraction filtering / Non-provable claim rejection. | **`PARTIALLY_DETECTED`** | Filtered during claim extraction; does not affect political memory, but incurs ingestion processing. |

---

## 3. Degradation Detectability Summary
- **Fully Detected Scenarios:** 4 / 6 (66.7%)
- **Partially Detected Scenarios:** 2 / 6 (33.3%)
- **Undetected Scenarios:** 0 / 6 (0.0%)
- **Epistemic Invariant:** Degraded sources cannot inflate political memory claims or corrupt corroborated evidence states.
