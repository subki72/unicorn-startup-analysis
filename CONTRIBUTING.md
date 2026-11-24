# Contributing Guidelines

Thank you for contributing to `unicorn-startup-analysis`.

## Development Setup

1. Clone the repository and create a virtual environment (Python 3.11+):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   make install
   ```
2. Copy environment configuration defaults:
   ```bash
   cp .env.example .env
   ```
3. Install pre-commit hooks (optional, recommended):
   ```bash
   pre-commit install
   ```

## Code Quality & Testing Standards

All pull requests targeting `main` must pass:
- **Ruff lint & formatting**: `python -m ruff check src tests main.py && python -m ruff format --check src tests main.py`
- **Flake8 check**: `python -m flake8 --max-line-length=120 src tests main.py`
- **Pytest suite**: `python -m pytest tests/ -v --cov=src --cov-fail-under=75`
- **Original notebook preservation**: `Unicorn_Analysis.ipynb` and `environment.yml` remain intact for Conda/Jupyter users unless a notebook-specific change is intended.

## Commit Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):
- `feat: ...` for new features
- `fix: ...` for bug fixes
- `test: ...` for test additions or updates
- `ci: ...` for CI/CD and container workflow changes
- `docs: ...` for documentation updates
