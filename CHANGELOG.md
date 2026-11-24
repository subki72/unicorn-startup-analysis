# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-24

### Added
- Modular Python package `src/unicorn_analytics/` preserving non-breaking dual-mode compatibility with `Unicorn_Analysis.ipynb` and `environment.yml`.
- Validated environment configuration (`AnalyticsSettings`) and structured leveled logging (`configure_logging`) with `.env.example`.
- Pydantic v2 request/response contracts (`UnicornRecord`, `CohortAnalysisRequest`, `AnalysisResponse`, `HealthResponse`, `ErrorResponse`).
- Versioned SQLite3 DDL migration (`migrations/001_unicorn_schema.sql`) and parameterized `UnicornRepository` with foreign keys, check constraints, and lock timeout safeguards.
- Analytics engine (`analyzer.py`) with capital efficiency ROI multiple (`valuation / funding`), bounded TTL response caching (`AnalysisCache`), and non-interactive `Agg` PNG chart exports.
- FastAPI microservice (`src/unicorn_analytics/api.py`) exposing `GET /health` and `POST /analyze` with `CORSMiddleware`, security headers, sliding-window rate limiting, and global exception masking.
- CLI runner (`main.py`) supporting `--companies`, `--seed`, `--top-n`, `--db-path`, `--export-json`, `--export-charts`, and `--health`.
- Five offline Pytest unit and integration suites (`tests/`) covering generator, repository, analyzer/CLI, schemas/config, and FastAPI endpoints.
- Production tooling: pinned `requirements.txt`, `requirements-lock.txt`, `uv.lock`, `pyproject.toml`, `.flake8`, `.pre-commit-config.yaml`, `Makefile`, multi-stage non-root `Dockerfile`, `docker-compose.yml`, GitHub Actions CI (`ci.yml`), Dependabot, governance docs, and `docs/RUNBOOK.md`.

### Fixed
- Eliminated 32-bit integer overflow on billion-scale valuations in synthetic data generation on Windows by enforcing explicit `numpy.int64` arrays and isolated per-call RNG/Faker seeding.
