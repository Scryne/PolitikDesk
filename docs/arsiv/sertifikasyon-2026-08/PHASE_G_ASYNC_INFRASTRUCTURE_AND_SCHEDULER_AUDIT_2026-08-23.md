# POLITIKDESK — PHASE G ASYNC INFRASTRUCTURE & SCHEDULER AUDIT
**Date:** 2026-08-23  
**Auditor:** Distributed Systems SRE  
**Status:** ASYNC INFRASTRUCTURE AUDITED & VERIFIED  

---

## 1. Executive Summary

This report evaluates asynchronous task scheduling, worker queue partitioning, Celery Beat cadence, and task expiration guards to ensure distributed tasks do not cause queue starvation or duplicate execution.

---

## 2. Worker Queue Partitioning & Beat Integrity

### 2.1 Queue Architecture
- **`default` Queue (`pd-worker`):** Fast ingestion, deduplication, event clustering, and SRE metric collection ($< 500\text{ms}$ tasks).
- **`llm` Queue (`pd-worker-llm`):** Dedicated worker for claim extraction and synthesis ($6\text{s}–60\text{s}$ LLM calls), preventing heavy AI calls from starving core database ingestion.

### 2.2 Celery Beat Schedule Table

| Task Name | Queue | Schedule Interval | Task Expiry (`expires`) | Operational Function |
| :--- | :---: | :---: | :---: | :--- |
| **`ingest_core_sources`** | `default` | 300 s (5 min) | 240 s | High-priority news & official RSS feeds. |
| **`ingest_social_sources`** | `social` | 600 s (10 min) | 500 s | Decoupled Twitter guest-token scraping. |
| **`cluster_events`** | `default` | 180 s (3 min) | 120 s | Centroid clustering of unlinked articles. |
| **`extract_claims`** | `llm` | 600 s (10 min) | 500 s | LLM claim extraction on new events. |
| **`evaluate_evidence`** | `default` | 300 s (5 min) | 240 s | Deterministic rule-based corroboration. |
| **`backup_daily`** | `default` | Daily (03:00 UTC) | 3600 s | Automated database dump & manifest. |

---

## 3. Queue Starvation & Drift Defenses
- **Expiration Bounding:** Every scheduled beat task defines `expires`, ensuring delayed or backed-up tasks self-terminate rather than creating thundering herds upon worker recovery.
- **Audit Verdict:** **`PASS (Clean queue partitioning and schedule integrity)`**.
