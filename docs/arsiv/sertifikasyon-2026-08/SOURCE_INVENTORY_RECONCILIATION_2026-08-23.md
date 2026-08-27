# POLITIKDESK — SOURCE INVENTORY RECONCILIATION REPORT
**Date:** 2026-08-23  
**Auditor:** Principal Data Platform Engineer & Source Intelligence Architect  
**Status:** RECONCILED & CANONICAL  

---

## 1. Executive Summary

This report establishes the single **canonical source count** for the PolitikDesk platform and reconciles all numerical ambiguities between historical documentation, vertical configuration files, and the production PostgreSQL database.

---

## 2. Canonical Source Inventory Baseline (Pre-Expansion)

Prior to Phase B expansion, PolitikDesk maintains exactly **90 active source configurations**.

### 2.1 File-Level Breakdown vs Item-Level Vertical Breakdown

| Configuration File | Declared `max_sources` | Declared `vertical` | Sources in File | Item-Level `vertical` Breakdown |
| :--- | :---: | :---: | :---: | :--- |
| `config/sources.yml` | **22** | `macro_economy` | **22** | `macro_economy`: 22 |
| `config/sources_legislation.yml` | **25** (22 active) | `legislation` | **22** | `legislation`: 22 |
| `config/sources_social.yml` | **50** (46 active) | `social` | **46** | `legislation`: 35, `macro_economy`: 11 |
| **TOTALS** | — | — | **90** | **`legislation`: 57, `macro_economy`: 33** |

---

## 3. Discrepancy Reconciliation

### 3.1 The "33 Macro vs 22" and "57 Legislation vs 22" Discrepancy
- **Root Cause:** Historical documentation in Phase A reported counts across two different grouping dimensions without explicit labeling:
  - **File Count Dimension:** `sources.yml` contains **22** sources; `sources_legislation.yml` contains **22** sources; `sources_social.yml` contains **46** sources ($22 + 22 + 46 = 90$).
  - **Entity Domain Dimension:** In `sources_social.yml`, each X account item defines its own target topic domain (`vertical: macro_economy` for economic figures like TCMB/HMB, and `vertical: legislation` for politicians and political parties).
    - Macro Economy total = 22 (from `sources.yml`) + 11 (from `sources_social.yml`) = **33 sources**.
    - Legislation total = 22 (from `sources_legislation.yml`) + 35 (from `sources_social.yml`) = **57 sources**.
- **Database Alignment:** 
  - `SELECT COUNT(*) FROM sources WHERE is_active = TRUE;` returns **90**.
  - `SELECT vertical, COUNT(*) FROM sources GROUP BY vertical;` returns `macro_economy: 33` and `legislation: 57`.
  - Set difference between Database Slugs and YAML Slugs is $\emptyset$ (`db_slugs - cfg_slugs == set()`).

---

## 4. Multi-Dimensional Canonical Baseline Matrix

```text
================================================================================
CANONICAL PRE-EXPANSION SOURCE INVENTORY (90 Sources)
================================================================================
By Tier:
  - Tier 1 (Official State / Central Bank / Stats)  : 9 sources
  - Tier 2 (Wire Agencies & Global Public Media)     : 5 sources
  - Tier 3 (National & Independent Journalism)      : 30 sources
  - Tier 4 (Social Media / Attribution Statements)  : 46 sources

By Kind:
  - official : 9 sources
  - wire     : 5 sources
  - media    : 30 sources
  - social   : 46 sources

By Adapter:
  - rss             : 36 sources
  - twitter         : 46 sources
  - tuik_sdmx       : 1 source  (TÜİK SDMX REST v2.1)
  - evds            : 1 source  (TCMB EVDS v3)
  - wp_rest         : 1 source  (HMB WordPress REST)
  - resmi_gazete    : 1 source  (Resmî Gazete Fihrist)
  - tbmm            : 1 source  (TBMM Bills & Minutes)
  - sayistay        : 1 source  (Sayıştay Audit Reports)
  - cumhurbaskanligi: 1 source  (TCCB Decrees)
  - generic_html    : 1 source  (T24 Politika)

By Access Method:
  - rss             : 36 sources
  - social          : 46 sources
  - official_feed   : 5 sources
  - api             : 2 sources
  - generic_html    : 1 source
================================================================================
```

---

## 5. Reconciliation Verdict
* **Discrepancy Status:** RESOLVED & CLARIFIED.
* **Canonical Count:** **90 Active Sources** prior to Phase B expansion.
* **Database / Configuration Synchronization:** 100% in sync, 0 orphan records.
