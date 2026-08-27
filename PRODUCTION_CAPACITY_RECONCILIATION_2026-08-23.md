# POLITIKDESK — PRODUCTION CAPACITY RECONCILIATION
**Date:** 2026-08-23  
**Auditor:** Production Infrastructure & Capacity Authority  
**Subject:** Memory Discrepancy Resolution & Hardware Envelope Re-Certification  

---

## 1. Executive Summary & Root Cause Analysis

During Day-0 production runtime measurements, real memory consumption across the active 7-container Docker Compose stack was measured at **1.95 GiB Aggregate RAM**, directly contradicting the historical "1 vCPU / 1 GB RAM" specification.

This discrepancy has been forensically analyzed. The root cause is the inclusion of local in-memory machine learning and bridge runtimes:
1. **Local PyTorch & Sentence-Transformers in `pd-worker` (948.7 MiB):** Holds embedding model weights in RAM for semantic deduplication.
2. **PostgreSQL 16 shared buffers & pgvector in `pd-db` (467.5 MiB):** Dedicated cache buffers and vector index allocations.
3. **RSSHub Node.js Runtime in `pd-rsshub` (296.1 MiB):** Headless bridge runtime for non-RSS sources.
4. **FastAPI, Celery Beat, Celery LLM, and Redis (240.2 MiB combined).**

$$\mathbf{Measured\ Aggregate\ Stack\ RAM} = \mathbf{1,952.5\ MiB\ (\approx 1.95\ GiB)}$$

---

## 2. Live Per-Container Measurement Ledger

```text
======================================================================================================
DAY-0 LIVE CONTAINER RESOURCE MEASUREMENTS (docker stats --no-stream)
======================================================================================================
Container Name  | Measured RSS Memory   | Memory % (of host) | CPU % (Idle/Ingest) | PIDs | Concurrency
----------------+-----------------------+--------------------+---------------------+------+------------
pd-worker       | 948.7 MiB             | 8.03%              | 5.41% / 28.5%       | 52   | 4 Workers
pd-db           | 467.5 MiB             | 3.96%              | 0.63% / 8.2%        | 12   | 20 Pool
pd-rsshub       | 296.1 MiB             | 2.51%              | 0.00% / 4.1%        | 31   | Node runtime
pd-worker-llm   | 119.3 MiB             | 1.01%              | 0.14% / 12.0%       | 7    | 1 Worker
pd-api          | 60.9 MiB              | 0.52%              | 0.16% / 2.5%        | 10   | Uvicorn ASGI
pd-beat         | 48.4 MiB              | 0.41%              | 0.00% / 0.1%        | 1    | 1 Scheduler
pd-redis        | 11.6 MiB              | 0.10%              | 0.42% / 1.8%        | 7    | In-memory
----------------+-----------------------+--------------------+---------------------+------+------------
TOTAL STACK     | 1,952.5 MiB (~1.95 GiB)| 16.54%             | ~6.8% (Idle)        | 120  | —
======================================================================================================
```

---

## 3. Deployment Profile Memory Analysis

- **Profile A (Minimal Core: API + DB + Redis):** **~540 MB RAM** *(Fits in 1 GB VPS, but lacks background ingestion workers)*.
- **Profile B (Cloud Embedding Mode — PyTorch removed, embeddings via API):** **~870 MB RAM** *(Fits tightly in 1 GB VPS, risky during batch spikes)*.
- **Profile C (Full Autonomous Production Stack — Local Embeddings + RSSHub Bridge):** **~1.95 GiB RAM** *(Requires $\ge 2\text{ GB}$ VPS)*.

---

## 4. Re-Certified Production Hardware Envelope

The previous "1 vCPU / 1 GB RAM / 10 GB Disk" claim is **superseded by empirical Day-0 measurements**:

```text
======================================================================================================
RE-CERTIFIED PRODUCTION HARDWARE ENVELOPE
======================================================================================================
Parameter                      | Minimum Viable Target             | Recommended Production Baseline
-------------------------------+-----------------------------------+----------------------------------
CPU Allocation                 | 2 vCPU                            | 2 to 4 vCPU
System RAM (Memory)            | 2 GB RAM (with 1 GB swap)         | 4 GB RAM (Zero swap dependency)
Disk Storage (SSD)             | 20 GB SSD                         | 25 to 50 GB SSD
Maximum Sustainable Sources    | 101 Sources (Measured)            | Up to 150 Sources
======================================================================================================
```

---

## 5. Storage Growth & Headroom Projections

- **Current Database Size (Day 0):** **308 MB** (11,038 articles, 14,484 evidence records).
- **Projected Daily Ingestion:** ~15–20 MB / day (raw text excerpts + vector embeddings).
- **30-Day Growth:** $+600\text{ MB}$ ($\approx 910\text{ MB}$ total DB).
- **90-Day Growth:** $+1.8\text{ GB}$ ($\approx 2.1\text{ GB}$ total DB).
- **365-Day Growth:** $+7.3\text{ GB}$ ($\approx 7.6\text{ GB}$ total DB).
- **Backup Overhead:** 30 daily compressed backups ($\approx 35\text{ MB} \times 30 = 1.05\text{ GB}$).
- **Docker Image Layer Footprint:** $\approx 4.2\text{ GB}$.
- **Safe Storage Ceiling:** **25 GB SSD** provides over 12 months of unpruned operation.

---

## 6. Terminology Calibration
- **RPO:** Formally designated as **`Configured Maximum Scheduled Data-Loss Window (<= 24h daily backup)`**.
- **Source Health:** Formally designated as **`101 Registered & Parser-Conformant Sources (Live network reachability actively monitored)`**.
