# POLITIKDESK — PHASE G FORENSIC DEPLOYMENT BASELINE REPORT
**Date:** 2026-08-23  
**Auditor:** Production Infrastructure SRE & Go-Live Auditor  
**Status:** FORENSIC DEPLOYMENT BASELINE CAPTURED  

---

## 1. Deployment Topology & Manifest Inventory

### 1.1 Derived Production Topology
```text
                          [ Ingress HTTPS / Reverse Proxy ]
                                         │ (TLS 443 / Strict CSP Nonce)
                                         ▼
                             [ pd-api / Web Server ]
                                  (FastAPI / Uvicorn)
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
 [ PostgreSQL 16 ]                 [ Redis 7.2 ]                   [ Celery Worker / Beat ]
 (pgvector, stat_statements)       (AOF Persistence, Auth)         (pd-worker, pd-worker-llm, pd-beat)
        │                                                                 │
        └────────────────────────────────┬────────────────────────────────┘
                                         ▼
                           [ External Ingestion Network ]
                           (49 Core Feeds, 46 Social, 6 APIs)
```

### 1.2 Infrastructure Manifests
- **Docker Compose:** `docker-compose.yml` (5 core services: `db`, `redis`, `migrate`, `api`, `worker`, `worker-llm`, `beat`).
- **Container Definition:** `Dockerfile` (Multi-stage layer caching, non-root `appuser` UID 1000, `certs/` inclusion).
- **Environment Templates:** `.env.example` (Comprehensive configuration contracts).
- **Migration Engine:** `migrations/` & `scripts.migrate` (Linear, reversible DDL versioning).
- **Disaster Recovery:** `scripts.backup` (`pg_dump` inside container, SHA-256 manifest verification, `--into` safe test restore).
- **Deployment Gate:** `scripts.check_deployment` (Release identity, code hash sync, beat schedule integrity).

---

## 2. Invariant Reconciliation
- Configured Sources (101) = Loaded Sources (101) = Expected Sources (101) = Database Records (101) (**PASS**).
- Zero silent headroom in `config/sources.yml` and `config/sources_legislation.yml`.
