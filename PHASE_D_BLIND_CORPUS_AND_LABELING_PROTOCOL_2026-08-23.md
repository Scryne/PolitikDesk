# POLITIKDESK — PHASE D BLIND CORPUS & LABELING PROTOCOL REPORT
**Date:** 2026-08-23  
**Auditor:** Information Integrity Researcher & Data Quality Auditor  
**Status:** PROTOCOL ESTABLISHED & EXECUTED  

---

## 1. Executive Summary

To avoid circular validation where an algorithm evaluates its own outputs, this report establishes a deterministic **Proxy Ground Truth Labeling Protocol** and an adversarial blind corpus constructed independently from the pipeline's code paths.

---

## 2. Deterministic Labeling Taxonomy

| Label Code | Label Name | Definition / Operational Boundary |
| :---: | :--- | :--- |
| **`EXACT_DUPLICATE`** | Birebir Tam Tekrar | Identical normalized token sequence; byte-level or whitespace-only differences. |
| **`NEAR_DUPLICATE`** | Yakın Tekrar / Editoryal Revizyon | $>80\%$ shared text with minor headline/intro alteration without new factual claims. |
| **`SYNDICATED_SHARED_ORIGIN`** | Ajans Kopyası / Ortak Köken | Verbatim wire dispatch republished by separate media outlets. |
| **`SAME_EVENT_INDEPENDENT`** | Aynı Olay / Bağımsız Habercilik | Same underlying news event described independently with distinct phrasing and structure. |
| **`DIFFERENT_EVENT`** | Farklı Olay / Bağımsız İçerik | Distinct topic, different entities, different dates, or conflicting numbers. |
| **`UNCERTAIN`** | Belirsiz / İnceleme Gerektiren | Ambiguous phrasing or incomplete snippet requiring human editorial review. |

---

## 3. Blind Corpus Sampling & Protocol Execution

- **Corpus Size:** 50 multi-source article pairs sampled across 7-day shadow ingestion window.
- **Provenance Classification:** **`PROXY GROUND TRUTH`** (derived from independent external cross-referencing and manual semantic validation).
- **Ambiguity Rule:** In cases of semantic uncertainty, pairs were flagged as `UNCERTAIN` and excluded from binary precision calculations to avoid bias.
