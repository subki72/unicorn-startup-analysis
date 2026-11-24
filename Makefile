.PHONY: install lint format test run cli health docker-build clean

PYTHON ?= python

install:
	$(PYTHON) -m pip install -r requirements.txt

lint:
	$(PYTHON) -m ruff check src tests main.py
	$(PYTHON) -m ruff format --check src tests main.py
	$(PYTHON) -m flake8 --max-line-length=120 src tests main.py

format:
	$(PYTHON) -m ruff format src tests main.py

test:
	$(PYTHON) -m pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=75

run:
	PYTHONPATH=src $(PYTHON) -m uvicorn unicorn_analytics.api:app --host 0.0.0.0 --port 8000 --reload

cli:
	$(PYTHON) main.py --companies 100 --db-path data/unicorns.db --export-json --export-charts

health:
	$(PYTHON) main.py --health

docker-build:
	docker build -t unicorn-startup-analysis:latest .

clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in list(pathlib.Path('.').rglob('__pycache__')) + [pathlib.Path('.pytest_cache'), pathlib.Path('.ruff_cache'), pathlib.Path('artifacts')]]"
