# Operations Runbook — Unicorn Startup Analytics

## 1. Service Overview

`unicorn-startup-analysis` operates in dual mode:
- **Interactive Notebook Mode**: `Unicorn_Analysis.ipynb` with `environment.yml` (preserved unchanged).
- **Production CLI & FastAPI Service**: `src/unicorn_analytics/` + `main.py` backed by SQLite3 (`migrations/001_unicorn_schema.sql`).

## 2. Health & Readiness Checks

- **HTTP Liveness Probe**:
  ```bash
  curl -fsS http://127.0.0.1:8000/health
  ```
  Expected response (`200 OK`):
  `{"status":"ok","service":"unicorn-startup-analysis","version":"1.0.0","db_backend":"sqlite3","schema_ready":true}`
- **CLI Readiness Probe**:
  ```bash
  make health
  ```

## 3. Configuration & Tuning

| Variable | Default | Operational Impact |
|---|---|---|
| `DB_PATH` | `:memory:` | SQLite file path or `:memory:` for stateless API analysis |
| `DB_TIMEOUT_SECONDS` | `10.0` | SQLite lock wait timeout under concurrent writes |
| `DEFAULT_NUM_COMPANIES` | `100` | Default synthetic cohort size for CLI runs |
| `RANDOM_SEED` | `42` | Reproducibility seed for synthetic cohorts |
| `ALLOWED_ORIGINS` | `http://localhost:3000,...` | Explicit CORS origin allowlist (wildcards rejected) |
| `RATE_LIMIT_PER_MINUTE` | `120` | Sliding-window request cap per client IP on `POST /analyze` |
| `CACHE_TTL_SECONDS` | `60` | Bounded TTL response cache window (`0` disables caching) |
| `LOG_LEVEL` | `INFO` | Structured log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## 4. Incident Playbook

### Symptom: HTTP `429 Too Many Requests` on `POST /analyze`
1. Inspect `Retry-After` response header and client IP frequency in logs (`Rate limit exceeded for client=...`).
2. If triggered by legitimate batch load, increase `RATE_LIMIT_PER_MINUTE` and restart the container.

### Symptom: HTTP `422 Unprocessable Entity` on `POST /analyze`
1. Check Pydantic validation message for invalid bounds (`num_companies` outside `1..5000`, `year_founded > date_joined.year`, or empty `records: []`).
2. Ensure custom records pass positive `valuation` and `funding` integers in USD.

### Symptom: HTTP `500 Internal Server Error` (`INTERNAL_ERROR`)
1. External clients receive masked JSON without stack traces.
2. Inspect container stdout logs for `Unhandled exception on POST /analyze` traceback.
3. Verify `migrations/001_unicorn_schema.sql` exists and `DB_PATH` parent directory is writable by UID `10001` (`appuser`).

### Symptom: SQLite `database is locked`
1. Increase `DB_TIMEOUT_SECONDS` (e.g., `20.0`) or route ephemeral API analysis to `DB_PATH=:memory:`.
2. Ensure no stale external process holds an exclusive file lock on the `.db` file.

## 5. Rollback Procedure

1. Roll back to the previous immutable container tag or Git release tag (`v1.0.0`):
   ```bash
   git checkout v1.0.0
   docker compose up -d --build
   ```
2. Re-verify `GET /health` returns `"schema_ready": true`.
