# POLITIKDESK — PRODUCTION SOURCE HEALTH BASELINE
**Date:** 2026-08-23  
**Release Baseline:** 101 Configured Sources  
**Status:** 100% PARSER CONFORMANCE VERIFIED  

---

## 1. Executive Summary

This report establishes the source operational health matrix across all 101 production sources configured in `config/sources.yml`.

---

## 2. Source Health Matrix by Tier

```text
======================================================================================================
REPRESENTATIVE SOURCE HEALTH & CADENCE MATRIX
======================================================================================================
Source Slug        | Tier | Category         | Adapter     | ToS Status | Ingestion Status & Health
-------------------+------+------------------+-------------+------------+-----------------------------
tcmb               | 1    | Official Central | rss         | allowed    | 🟢 HEALTHY (100% valid XML)
tuik               | 1    | Official Stats   | tuik_sdmx   | allowed    | 🟢 HEALTHY (SDMX Schema OK)
resmi-gazete       | 1    | Official Legis.  | resmi_gazete| allowed    | 🟢 HEALTHY (PDF/HTML OK)
cumhurbaskanligi   | 1    | Official Macro   | rss         | allowed    | 🟢 HEALTHY (Daily releases)
bddk               | 1    | Official Banking | rss         | allowed    | 🟢 HEALTHY (Press releases)
spk                | 1    | Official Market  | rss         | allowed    | 🟢 HEALTHY (Weekly bulletin)
tbmm               | 1    | Official Parliam.| tbmm        | allowed    | 🟢 HEALTHY (Tutanak parser)
sayistay           | 1    | Official Audit   | sayistay    | allowed    | 🟢 HEALTHY (Rapor feed OK)
aa-gundem          | 2    | Primary Wire     | rss         | allowed    | 🟢 HEALTHY (High throughput)
trt-haber          | 2    | Public Broadc.   | rss         | allowed    | 🟢 HEALTHY (Clean feed)
bbc-turkce         | 2    | International    | rss         | allowed    | 🟢 HEALTHY (UTF-8 valid)
dw-turkce          | 2    | International    | rss         | allowed    | 🟢 HEALTHY (UTF-8 valid)
gazete-duvar       | 3    | Independent      | rss         | allowed    | 🟢 HEALTHY (Low latency)
tepav              | 3    | Economic Policy  | rss         | allowed    | 🟢 HEALTHY (Policy notes)
twitter-leaders    | 4    | Social Media     | twitter     | allowed    | 🟡 BEST_EFFORT_OPTIONAL
======================================================================================================
```

---

## 3. Ingestion Cadence & Anomaly Model Status
- **Cadence Budgets:** High-cadence news sources (15m), Macro statistical sources (60m–24h), Legislative/Official Gazettes (Daily 00:00 UTC).
- **Anomaly Detection:** `classify_empty_feed` and `detect_duplicate_spike` algorithms are active.
