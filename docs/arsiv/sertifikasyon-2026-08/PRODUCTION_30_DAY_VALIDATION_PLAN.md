# POLITIKDESK — 30-DAY PRODUCTION VALIDATION PLAN
**Date:** 2026-08-23  
**Target Duration:** Day 1 through Day 30  
**Status:** ACTIVE OPERATIONAL MONITORING (2–4 GB RAM Target)  

---

## 1. Objective

To monitor, validate, and record the real-world operational health of PolitikDesk over 30 continuous calendar days under live Turkish political news and macro-economic data feeds.

---

## 2. Daily Metric Collection Ledger

Every 24 hours at 04:00 UTC, the on-call SRE logs:

| Metric Category | Telemetry Source | Healthy Target (GREEN) | Warning Target (YELLOW) | Critical Action (RED) |
| :--- | :--- | :--- | :--- | :--- |
| **API Availability** | `/livez` & `/readyz` | 100% uptime ($p99 < 15\text{ms}$) | 1–3 failed probes / day | $>5\text{ min}$ cumulative 503 |
| **Ingestion Health** | `/admin/pipeline-health` | $\ge 90$ active sources | $75–89$ active sources | $<75$ active sources |
| **Queue Latency** | Redis `llen('celery')` | 0–10 backlog | 11–100 backlog | $>100$ items ($>10\text{m}$) |
| **Memory Ceiling** | Container RSS | Stack total $\le 2.4\text{ GB}$ | $2.4\text{ GB} - 3.2\text{ GB}$ | Stack $>3.4\text{ GB}$ (OOM risk)|
| **Database Growth** | `pg_database_size` | $+15–25\text{ MB / day}$ | $>50\text{ MB / day}$ | Disk usage $>80\%$ |
| **Backup Freshness** | `backups/` directory | $\le 24\text{ hours}$ old | $24–30\text{ hours}$ old | $>30\text{ hours}$ without backup |
| **Epistemic Errors** | `scripts.production_gates`| 0 orphan records | 0 orphan records | $\ge 1$ orphan record |

---

## 3. Operational State Definitions

- **🟢 OPERATIONAL-GREEN:** All 7 services healthy, $\ge 90$ sources ingesting, 0 queue backlog, 0 orphan records, backup verified $\le 24\text{h}$.
- **🟡 OPERATIONAL-YELLOW:** 1–3 non-official sources experiencing upstream timeouts / circuit open, or queue backlog transiently elevated.
- **🔴 OPERATIONAL-RED:** Database or Redis unreachable, API returning 503, Celery queue starvation $>15\text{m}$, or backup missed $>30\text{h}$. Trigger SOP-01/SOP-04.
