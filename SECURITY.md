# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in this repository:

1. **Do NOT open a public GitHub issue** for undisclosed vulnerabilities.
2. Submit a private report via GitHub Security Advisories (`Security -> Advisories -> Report a vulnerability`).
3. Include affected file paths, line numbers, reproduction steps, and estimated severity.
4. Initial acknowledgement will be provided within **48 hours**.

## Security Controls

- **Secret Hygiene**: `.env`, `.env.*`, key files, and local `.db` artifacts are excluded via `.gitignore`.
- **SQL Injection Prevention**: All SQLite3 reads and writes use parameterized queries with bound parameters (`?`) and database-level `CHECK` / `FOREIGN KEY` constraints.
- **Input & HTTP Hardening**: Strict Pydantic v2 request schemas, sliding-window rate limiting, explicit `ALLOWED_ORIGINS` CORS allowlist, security response headers, and global exception masking.
- **Automated Vulnerability Management**: Weekly Dependabot alerts (`semver-major` ignored for stability), Semgrep SAST, and Trivy container image scanning in CI.
- **Container Hardening**: Multi-stage non-root Docker builds (`appuser` UID 10001).
