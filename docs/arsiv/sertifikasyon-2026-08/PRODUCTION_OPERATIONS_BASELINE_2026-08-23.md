# POLITIKDESK — PRODUCTION OPERATIONS BASELINE
**Date:** 2026-08-23  
**Release SHA:** `678e06b94505`  
**Operational Status:** OPERATIONAL-GREEN (Reconciled Hardware: 2–4 GB RAM)  

---

## 1. Executive Operational Overview

This report documents the Day-0 runtime baseline of PolitikDesk operating as a multi-container stack in Docker Compose.

---

## 2. Release & Container Fleet Baseline

```text
======================================================================================================
FLEET INVENTORY & RUNTIME BASELINE
======================================================================================================
Service Name    | Image Repository & Tag   | Container ID / State | Uptime     | Port Binding
----------------+--------------------------+----------------------+------------+----------------------
pd-api          | politikdesk-api:latest   | Healthy (10 PIDs)    | Up 20m     | 127.0.0.1:8000
pd-worker       | politikdesk-worker:latest| Running (52 PIDs)    | Up 20m     | Internal
pd-worker-llm   | politikdesk-worker-llm:..| Running (7 PIDs)     | Up 20m     | Internal
pd-beat         | politikdesk-beat:latest  | Running (1 PID)      | Up 20m     | Internal
pd-db           | pgvector/pgvector:pg16   | Healthy (12 PIDs)    | Up 2h      | 127.0.0.1:5432
pd-redis        | redis:7-alpine           | Healthy (7 PIDs)     | Up 2h      | 127.0.0.1:6379
pd-rsshub       | diygod/rsshub:latest     | Running (31 PIDs)    | Up 2h      | 127.0.0.1:1200
======================================================================================================
```

---

## 3. Reconciled Hardware & Resource Profile
- **Active Sources:** 101 registered & parser-conformant sources.
- **Database Metrics:** 308 MB disk footprint, 11,038 articles, 14,484 evidence links (0 orphan records).
- **Redis Memory:** 2.43 MB used, 0 queue backlog.
- **Aggregate Fleet RAM:** **1.95 GiB** (PyTorch in `pd-worker`, pgvector in `pd-db`, Node.js in `pd-rsshub`).
- **Certified Deployment Target:** **2 vCPU / 4 GB RAM / 25 GB SSD** (Minimum Viable: 2 GB RAM).
