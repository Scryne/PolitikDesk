# POLITIKDESK — PRODUCTION OPERATIONAL RUNBOOK

**Target Audience:** Production SREs, On-Call Engineers, Platform Administrators  
**Applicability:** Production & Staging Environments  
**Revision:** 2026-08-23 (Phase G Certified)  

---

## 1. System Overview & Deployment Architecture

PolitikDesk runs as a multi-container stack orchestrated via Docker Compose:
- **`pd-db`**: PostgreSQL 16 with `pgvector` and `pg_stat_statements`.
- **`pd-redis`**: Redis 7.2 AOF with password authentication.
- **`pd-migrate`**: Ephemeral schema migration container.
- **`pd-api`**: FastAPI Web & API server on Uvicorn.
- **`pd-worker`**: Celery worker for fast ingestion, dedup, and event clustering.
- **`pd-worker-llm`**: Dedicated Celery worker for LLM claim extraction and synthesis.
- **`pd-beat`**: Celery Beat periodic task scheduler.

---

## 2. Environment Variables & Secret Configuration

Create `/home/appuser/.config/politikdesk/.env` (or set `PD_ENV_FILE`):

```bash
# Core Environment
PD_ENV=production
PD_APP_VERSION=0.1.0
PD_API_TOKEN=your-random-production-token-at-least-32-chars
PD_SESSION_SECRET=your-random-session-secret-key-32-chars

# Database & Redis Credentials
PD_DB_USER=politikdesk
PD_DB_PASS=strong-unique-postgres-password
PD_DB_NAME=politikdesk
PD_DATABASE_URL=postgresql://politikdesk:strong-unique-postgres-password@db:5432/politikdesk
PD_REDIS_PASSWORD=strong-unique-redis-password
PD_REDIS_URL=redis://:strong-unique-redis-password@redis:6379/0

# LLM Providers (Optional for Claim Extraction)
ANTHROPIC_API_KEY=sk-ant-api03-...
```

---

## 3. Standard Deployment Procedure

### 3.1 Initial Bootstrap & Database Migration
```bash
# 1. Build and start database and Redis
docker compose up -d db redis

# 2. Wait for db healthy, then run migrations
docker compose run --rm migrate

# 3. Start web API and async workers
docker compose up -d api worker worker-llm beat

# 4. Verify deployment health
curl -f http://127.0.0.1:8000/readyz
python -m scripts.check_deployment
```

---

## 4. Health & Monitoring Endpoints

- **Liveness Probe:** `GET /livez` $\to$ Returns `200 OK` (`{"status": "alive"}`).
- **Readiness Probe:** `GET /readyz` $\to$ Returns `200 OK` or `503 Service Unavailable` if PostgreSQL or Redis are down.
- **Prometheus Telemetry:** `GET /metrics` $\to$ OpenMetrics format for scraping.
- **SRE & Pipeline Dashboard:** `GET /admin/` and `GET /admin/pipeline-health`.

---

## 5. Incident Response Standard Operating Procedures (SOP)

### SOP-1: Source Circuit Breaker Tripped (State: OPEN)
- **Symptom:** Source log shows `circuit_tripped_open` with repeated HTTP 5xx or timeouts.
- **Action:** Inspect `/admin/circuits` to identify the failing source host. Verify upstream website reachability. Circuit automatically transitions to `HALF_OPEN` after 60s cooldown. No manual restart required.

### SOP-2: Empty Feed Anomaly Alert (`EMPTY_ANOMALY`)
- **Symptom:** SRE alert triggers for high-volume source producing 0 items.
- **Action:** Check if the publisher restructured RSS XML schema. Run `python -m scripts.ingest --slug <slug>` in debug mode.

### SOP-3: Duplicate Volume Spike Alert (`ANOMALOUS`)
- **Symptom:** Alert triggers on feed with $\ge 85\%$ duplicate ratio.
- **Action:** Verify whether the publisher experienced a pagination loop or republished historic archives.

### SOP-4: Celery Queue Starvation or Worker Crash
- **Symptom:** `/admin/pipeline-health` cards turn amber/red with increasing backlog.
- **Action:**
  ```bash
  docker compose restart worker worker-llm
  python -m scripts.drain_pipeline
  ```

---

## 6. Disaster Recovery & Backup Procedures

### 6.1 Creating an On-Demand Backup
```bash
python -m scripts.backup create --label manual_pre_upgrade
```

### 6.2 Restoring from Backup into Test Target
```bash
python -m scripts.backup verify backups/politikdesk_backup_*.sql.gz
python -m scripts.backup restore backups/politikdesk_backup_*.sql.gz --into politikdesk_recovery_test
```

---

## 7. Operational Boundaries & Known Limitations

1. **Twitter / Social Ingestion:** Classified as `BEST_EFFORT_OPTIONAL`. Decoupled from SRE alerting and restricted to Tier 4 single-source attribution.
2. **Short Municipal Template Merges:** Short notices ($<15$ words) with named-entity substitutions without numbers exhibit near-duplicate sensitivity; mitigated by downstream 48h event window.
3. **Scaling Beyond 250 Sources:** Requires PgBouncer connection pooling (`POSTGRES_POOL_SIZE = 30`) and Source Adapter Framework (SAF) queue partitioning.
