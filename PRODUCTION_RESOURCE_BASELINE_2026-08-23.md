# POLITIKDESK — PRODUCTION RESOURCE BASELINE
**Date:** 2026-08-23  
**Measurement Environment:** Live Docker Compose Container Fleet  
**Status:** DAY-0 RESOURCE PROFILE ESTABLISHED & RECONCILED  

---

## 1. Executive Summary

This report establishes the baseline resource utilization (CPU, Resident Set Size Memory, PIDs, and DB Connections) measured directly from the active 7-container production stack. 

> [!IMPORTANT]
> **Capacity Reconciliation:** Empirical Day-0 measurements establish total stack RAM at **~1.95 GiB** (driven by PyTorch in `pd-worker`, pgvector in `pd-db`, and Node.js in `pd-rsshub`). The certified production hardware baseline is formally updated from 1 GB to **2 vCPU / 4 GB RAM / 25 GB SSD** (Minimum Viable: 2 GB RAM).

---

## 2. Container Resource Footprint (Day 0 Live Measurement)

```text
======================================================================================================
LIVE CONTAINER RESOURCE UTILIZATION (Measured via Docker Engine API)
======================================================================================================
Container Name  | Role & Responsibility    | CPU %   | Resident Memory (RSS) | PIDs | Bound Port
----------------+--------------------------+---------+-----------------------+------+-----------------
pd-worker       | Fast Ingestion & SimHash | 5.41%   | 948.7 MiB (PyTorch)   | 52   | Internal
pd-db           | PostgreSQL 16 + pgvector | 0.63%   | 467.5 MiB             | 12   | 127.0.0.1:5432
pd-rsshub       | Bridge for Static Feeds  | 0.00%   | 296.1 MiB             | 31   | 127.0.0.1:1200
pd-worker-llm   | LLM Claim Extraction     | 0.14%   | 119.3 MiB             | 7    | Internal
pd-api          | FastAPI Web / API ASGI   | 0.16%   | 60.9 MiB              | 10   | 127.0.0.1:8000
pd-beat         | Celery Beat Scheduler    | 0.00%   | 48.4 MiB              | 1    | Internal
pd-redis        | Redis 7.2 AOF In-Memory  | 0.42%   | 11.6 MiB              | 7    | 127.0.0.1:6379
----------------+--------------------------+---------+-----------------------+------+-----------------
TOTAL STACK     | Full Fleet Footprint     | ~6.8%   | 1,952.5 MiB (~1.95 GiB)| 120 | —
======================================================================================================
```

---

## 3. Reconciled Hardware Targets & Alert Thresholds
- **Minimum Viable Hardware:** **2 vCPU / 2 GB RAM (with swap) / 20 GB SSD**
- **Recommended Production Baseline:** **2 to 4 vCPU / 4 GB RAM / 25 to 50 GB SSD**
- **Database Footprint:** **308 MB** initial; projected $+600\text{ MB}$ over 30 days.
- **Alerting Thresholds:** Warning at Stack RAM $> 2.8\text{ GB}$, Critical at $> 3.4\text{ GB}$.
