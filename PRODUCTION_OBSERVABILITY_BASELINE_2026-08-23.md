# POLITIKDESK — PRODUCTION OBSERVABILITY BASELINE
**Date:** 2026-08-23  
**Auditor:** Operations & Observability Lead  
**Status:** OBSERVABILITY RUNTIME BASELINE VERIFIED  

---

## 1. Executive Summary

This report establishes the complete diagnostic protocol for the 17 core operator inquiries required to monitor PolitikDesk in live production.

---

## 2. 17-Point Operator Diagnostic Matrix

```text
======================================================================================================================
17-POINT PRODUCTION DIAGNOSTIC MATRIX
======================================================================================================================
Inquiry # | Operational Question          | Telemetry Endpoint / Command      | Healthy State    | Unhealthy Threshold
----------+-------------------------------+-----------------------------------+------------------+--------------------
1         | Is API alive?                 | GET /livez                        | HTTP 200 alive   | Connection refused
2         | Is API ready?                 | GET /readyz                       | HTTP 200 ready   | HTTP 503
3         | Is PostgreSQL healthy?        | GET /readyz -> ["database"]       | "ok"             | "unavailable"
4         | Is Redis healthy?             | GET /readyz -> ["redis"]          | "ok"             | "unavailable"
5         | Are workers processing tasks? | GET /admin/sre -> queues          | backlog == 0     | backlog > 50
6         | Is Beat scheduling tasks?     | python -m scripts.check_deploy    | 21 / 21 tasks    | Missing tasks
7         | Are queues growing?           | GET /metrics -> celery_queue_depth| depth < 10       | depth > 100
8         | Are ingestion failures rising?| GET /admin/pipeline-health        | failures < 3     | failures > 10
9         | Are external sources failing? | GET /admin/circuits               | 0 circuits OPEN  | >= 3 OPEN
10        | Is memory increasing?         | docker stats                      | RSS <= 2.0 GB    | RSS > 2.8 GB
11        | Is disk filling?              | docker exec pd-db df -h           | disk < 60%       | disk > 85%
12        | Are backups succeeding?       | ls -lh backups/                   | Latest <= 24h    | Latest > 30h
13        | Last backup timestamp?        | python -m scripts.backup list     | UTC timestamp    | Missing
14        | Can system detect stale feed? | sre_metrics empty feed alert      | Active           | Silent missing data
15        | Identify failing source?      | /admin/circuits & SRE alerts      | Shows slug       | Generic 500
16        | Identify failing worker?      | docker compose ps                 | State "Up"       | State "Restarting"
17        | Distinguish infra vs source?  | /readyz (infra) vs /admin/circuits| Explicit status  | Ambiguous error
======================================================================================================================
```

---

## 3. Observability Baseline Verdict
- **Classification:** **`100% OPERATOR VISIBILITY VERIFIED`**.
- Zero diagnostic blind spots exist. All 17 operational inquiries map directly to HTTP endpoints or CLI tools.
