# Unicorn Startup Ecosystem Analysis

[![CI Pipeline](https://github.com/subki72/unicorn-startup-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/subki72/unicorn-startup-analysis/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

## Project Overview

This repository delivers an end-to-end **Unicorn Startup Ecosystem Analytics** platform backed by a normalized SQLite3 relational model (`unicorn_companies`, `unicorn_industries`, `unicorn_funding`, and `unicorn_dates`).

It preserves **100% dual-mode compatibility**:
- **Interactive Notebook Mode**: `Unicorn_Analysis.ipynb` and `environment.yml` remain untouched for Conda and Jupyter exploration.
- **Production CLI & FastAPI Service**: `src/unicorn_analytics/`, `migrations/001_unicorn_schema.sql`, and `main.py` extract the ETL, SQL aggregation, ROI analytics, and chart export pipeline into a typed, tested, containerized microservice.

## Business Questions Answered

1. **Industry Dominance**: Which industry sectors produce the largest concentration of unicorn startups, total valuation (`$B`), and capital efficiency (`valuation / funding`)?
2. **Top Valuations & Decacorns**: Which companies hold the highest valuations (`$B`), where are they headquartered, and how many reach decacorn scale (`>= $10B`)?
3. **Historical Growth Trends**: How has the annual cohort of newly crowned unicorns and cumulative valuation evolved over time?

## Architecture & Project Structure

```text
unicorn-startup-analysis/
├── .github/
│   ├── workflows/ci.yml          # Ruff, Flake8, Pytest + coverage, Semgrep, Docker, Trivy
│   └── dependabot.yml            # Weekly pip & GitHub Actions security updates
├── docs/
│   └── RUNBOOK.md                # Operational procedures & incident playbook
├── migrations/
│   └── 001_unicorn_schema.sql    # Versioned SQLite3 DDL schema & indexes
├── src/unicorn_analytics/
│   ├── __init__.py               # Public package exports
│   ├── config.py                 # AnalyticsSettings & structured leveled logging
│   ├── schemas.py                # Pydantic v2 request/response & chronology validation
│   ├── generator.py              # Isolated deterministic 64-bit dataset generator
│   ├── repository.py             # Parameterized SQLite3 persistence & analytics queries
│   ├── analyzer.py               # Pipeline orchestration, TTL cache & Agg chart export
│   └── api.py                    # FastAPI microservice (/health, /analyze, CORS, rate limit)
├── tests/                        # 5 offline unit & integration Pytest suites
├── main.py                       # CLI runner (--companies, --db-path, --health, exports)
├── Unicorn_Analysis.ipynb        # Original exploratory ETL & visualization notebook
├── environment.yml               # Original Conda environment specification
├── requirements.txt              # Exact pinned Python 3.11 dependencies
├── uv.lock                       # Cross-platform dependency lockfile
├── pyproject.toml                # Ruff, Pytest, Coverage, and package configuration
├── Dockerfile                    # Multi-stage non-root runtime (appuser UID 10001)
├── docker-compose.yml            # Local containerized service orchestration
└── Makefile                      # Single-command install, lint, test, run, and build tasks
```

## Quickstart (Makefile & CLI)

1. **Clone and configure environment**:
   ```bash
   git clone https://github.com/subki72/unicorn-startup-analysis.git
   cd unicorn-startup-analysis
   cp .env.example .env
   make install
   ```

2. **Verify SQLite schema readiness**:
   ```bash
   make health
   ```

3. **Run the ETL & Analytics CLI**:
   ```bash
   make cli
   ```
   Or customize options directly:
   ```bash
   python main.py --companies 200 --seed 42 --top-n 10 --db-path data/unicorns.db --export-json --export-charts
   ```

4. **Run quality checks and automated tests**:
   ```bash
   make lint
   make test
   ```

## FastAPI Microservice

Start the local API server:
```bash
make run
```

Or run via Docker Compose:
```bash
docker compose up --build
```

### Endpoints

- **`GET /health`**: Liveness and SQLite schema readiness check.
- **`POST /analyze`**: Runs synthetic or custom unicorn cohorts through parameterized SQLite3 aggregations and returns `CohortMetrics`, `industry_distribution`, `top_valuations`, and `yearly_trends`.

Example request:
```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"num_companies": 100, "random_seed": 42, "top_n": 5}'
```

## Legacy Jupyter Notebook Mode

To reproduce the original exploratory notebook workflow via Conda:
```bash
conda env create -f environment.yml
conda activate unicorn_env
jupyter notebook Unicorn_Analysis.ipynb
```

## Governance & Operations

- [Operations Runbook](./docs/RUNBOOK.md)
- [Security Policy](./SECURITY.md)
- [Contributing Guidelines](./CONTRIBUTING.md)
- [Changelog](./CHANGELOG.md)
- [MIT License](./LICENSE)
