# POLITIKDESK — PHASE C EPISTEMIC & CORROBORATION RED TEAM REPORT
**Date:** 2026-08-23  
**Auditor:** Independent Information Integrity Researcher & Red Team Lead  
**Status:** ADVERSARIAL TESTING COMPLETE — VERIFIED ROBUST  

---

## 1. Executive Summary

This report evaluates the resilience of PolitikDesk's evidence and corroboration models against adversarial inflation attacks.

We subjected the `independence_key` resolution architecture (`wire:<slug> \succ grp:<group> \succ src:<slug>`) to 5 adversarial edge cases to determine whether false corroboration or epistemic degradation can occur.

---

## 2. Adversarial Red Team Cases

### Case A — Multi-Channel Institutional Ingestion
- **Attack:** An official institution (TCMB or HMB) publishes identical information via Website RSS, EVDS API, and Press Release Feed.
- **Result:** **`DEFENSE SUCCESS`**. All channels map to `grp:official-tcmb`. `independent_count` remains 1. No artificial R2 green corroboration.

### Case B — Parent Conglomerate Multi-Brand Ingestion
- **Attack:** Demirören Media Group publishes the same economic story across 3 distinct brand domains (Hürriyet, Milliyet, CNN Türk).
- **Result:** **`DEFENSE SUCCESS`**. All articles map to `grp:media-demiroren`. Independent evidence count remains 1.

### Case C — Wire Agency Syndication
- **Attack:** Anadolu Ajansı wire dispatch republished verbatim or with minor intro edits by 10 client publishers.
- **Result:** **`DEFENSE SUCCESS`**. All 10 syndicated copies collapse into `wire:aa-ekonomi`. Independent count remains 1.

### Case D — Genuine Multi-Source Consensus
- **Attack:** 4 independent publishers with distinct ownership (TCMB Official + BBC Türkçe + DW Türkçe + Sözcü) report on the same event.
- **Result:** **`DEFENSE SUCCESS`**. System correctly computes `independent_count == 4`, legitimately granting R2 Green Corroboration.

### Case E — Official Primary Statement + Independent Investigative Reporting
- **Attack:** An official ministry issues a press statement, and an independent newspaper publishes an investigative piece referencing the same event.
- **Result:** **`DEFENSE SUCCESS`**. The system treats the official statement as `grp:official-<ministry>` (Tier 1) and the investigative reporting as `grp:media-<newspaper>` (Tier 3), yielding 2 independent perspectives with clear provenance separation.

---

## 3. Corroboration Quality vs Volume Analysis

- **Epistemic Principle:** 1 Tier 1 Primary Source + 1 Independent Confirmation $>$ 10 Syndicated Agency Echoes.
- **Verification:** In `politikdesk/evidence/rules.py`, R2 status explicitly requires at least one Tier 1/2 primary source and $\ge 2$ independent groups. Ten syndicated Tier 3 articles can NEVER trigger R2 corroboration without an underlying Tier 1/2 primary anchor or $\ge 3$ distinct independent groups.
- **Verdict:** Provenance and evidence quality invariants are strictly preserved.
