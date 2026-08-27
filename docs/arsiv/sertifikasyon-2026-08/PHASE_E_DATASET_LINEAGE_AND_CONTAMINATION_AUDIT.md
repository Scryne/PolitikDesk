# POLITIKDESK — PHASE E DATASET LINEAGE & CONTAMINATION AUDIT
**Date:** 2026-08-23  
**Auditor:** Adversarial Independent Forensic Reviewer  
**Status:** CONTAMINATION AUDIT COMPLETE  

---

## 1. Executive Summary

This report performs a strict dataset lineage audit across all evaluation corpora used in Phases A through D, classifying each sample by its provenance and potential contamination level.

---

## 2. Dataset Sample Lineage Breakdown

| Sample ID / Pair | Description | Phase Introduced | Lineage Classification | Contamination Finding |
| :--- | :--- | :---: | :---: | :--- |
| **S01** | TCMB %50 faiz sabit (Identical copy) | Phase B | `REGRESSION-DERIVED` | Present in unit test suite. |
| **S02** | TÜİK vs Türkiye İstatistik Kurumu | Phase C | `POST-REMEDIATION` | Contaminated: Hardcoded into `_CANONICAL_ACRONYMS`. |
| **S03** | Bakan Şimşek bütçe programı (Syndicated) | Phase C | `PREVIOUS-HOLDOUT-DERIVED` | Used in Phase C hold-out test. |
| **S04** | BDDK net kârı %12 arttı (Syndicated) | Phase C | `PREVIOUS-HOLDOUT-DERIVED` | Used in Phase C hold-out test. |
| **S05** | Resmî Gazete KDV değişikliği (Syndicated) | Phase C | `PREVIOUS-HOLDOUT-DERIVED` | Used in Phase C hold-out test. |
| **S06** | PPK pas geçme / Ekonomist yorumu (Indep) | Phase C | `PREVIOUS-HOLDOUT-DERIVED` | Used in Phase C hold-out test. |
| **S07** | Vergi paketi TBMM / Muhalefet eleştirisi | Phase C | `PREVIOUS-HOLDOUT-DERIVED` | Used in Phase C hold-out test. |
| **S08** | Kabine toplantısı / İş dünyası talebi | Phase C | `PREVIOUS-HOLDOUT-DERIVED` | Used in Phase C hold-out test. |
| **S09** | Hazine 2y 15 milyar vs 5y 12 milyar | Phase C | `POST-REMEDIATION` | Contaminated: Used to derive `_NUM_RE` guard. |
| **S10** | TCMB 50 milyar vs 80 milyar repo | Phase C | `POST-REMEDIATION` | Contaminated: Used to derive `_NUM_RE` guard. |
| **S11** | TCMB Ocak %45 vs Şubat %45 PPK | Phase C | `POST-REMEDIATION` | Contaminated: Used to derive `_MONTH_TOKENS`. |
| **S12** | TÜİK Ocak 6.70 vs Şubat 4.53 TÜFE | Phase C | `POST-REMEDIATION` | Contaminated: Used to derive `_MONTH_TOKENS`. |
| **S13** | İBB Meclis Ulaşım vs Kira yardımı | Phase C | `PREVIOUS-HOLDOUT-DERIVED` | Used in Phase C hold-out test. |
| **S14** | AYM 703 KHK vs Sendikalar Kanunu | Phase C | `PREVIOUS-HOLDOUT-DERIVED` | Used in Phase C hold-out test. |

---

## 3. Contamination Assessment

- **Total Samples in Phase C/D Hold-Out:** 14 pairs
- **Contaminated by Direct Post-Hoc Derivation:** **5 / 14 (35.7%)**
- **Truly Unseen Samples in Phase D Evaluation:** **0 / 14 (0.0%)**
- **Conclusion:** Phase D's reported "100% Precision / 0% FNR" was evaluated on a 100% contaminated dataset. A truly unseen challenge set is strictly required.
