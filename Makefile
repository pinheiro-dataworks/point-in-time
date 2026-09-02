# ===========================================================================
# Point-in-Time Analytics Lab
# ===========================================================================
# One entry point for every stage of the pipeline. Every target is safe to
# re-run - ingestion truncates rather than drops, and the SQL build scripts
# are idempotent.
#
# Quickstart:
#   make setup          # venv + dependencies
#   make warehouse-up   # start Postgres (docker compose) if not using a native install
#   make all             # ingest -> build -> export -> benchmark -> dbt
#   make dashboard        # run the Streamlit app locally
# ===========================================================================

PYTHON := .venv/Scripts/python.exe
DBT    := .venv/Scripts/dbt.exe
PIP    := .venv/Scripts/pip.exe

.PHONY: help setup warehouse-up warehouse-down ingest build export benchmark \
        dbt-deps dbt-seed dbt-run dbt-snapshot dbt-test dbt-build dbt-docs \
        dashboard test lint format all clean

help:
	@echo "Point-in-Time Analytics Lab"
	@echo ""
	@echo "  make setup          Create .venv and install requirements-dev.txt"
	@echo "  make warehouse-up   Start PostgreSQL via docker compose"
	@echo "  make warehouse-down Stop the docker compose warehouse"
	@echo "  make ingest         Load Bronze layer from raw CSV (python -m pit_lab.ingest)"
	@echo "  make build          Build Silver + Gold layers (python -m pit_lab.build)"
	@echo "  make export         Export Gold layer to data/processed/*.parquet"
	@echo "  make benchmark      Run EXPLAIN ANALYZE benchmarks, write docs/performance.md"
	@echo "  make dbt-build      dbt seed + snapshot + run + test"
	@echo "  make dbt-docs       Generate and serve dbt docs"
	@echo "  make dashboard      Run the Streamlit dashboard locally"
	@echo "  make test           Run the pytest suite"
	@echo "  make lint           Run ruff check + format --check"
	@echo "  make all            ingest -> build -> export -> benchmark -> dbt-build"
	@echo "  make clean          Remove venv, target/, __pycache__, dbt logs"

setup:
	python -m venv .venv
	$(PIP) install --upgrade pip setuptools wheel --quiet
	$(PIP) install -r requirements-dev.txt
	$(PYTHON) -m pip install -e . --quiet
	@if not exist .env copy .env.example .env
	@echo "Setup complete. Edit .env if your Postgres credentials differ from the defaults."

warehouse-up:
	docker compose up -d
	@echo "Waiting for Postgres to accept connections..."

warehouse-down:
	docker compose down

ingest:
	$(PYTHON) -m pit_lab.ingest

build:
	$(PYTHON) -m pit_lab.build

export:
	$(PYTHON) -m pit_lab.export

benchmark:
	$(PYTHON) -m pit_lab.benchmark

dbt-deps:
	$(DBT) deps --project-dir dbt_pit --profiles-dir .

dbt-seed:
	$(DBT) seed --project-dir dbt_pit --profiles-dir .

dbt-run:
	$(DBT) run --project-dir dbt_pit --profiles-dir .

dbt-snapshot:
	$(DBT) snapshot --project-dir dbt_pit --profiles-dir .

dbt-test:
	$(DBT) test --project-dir dbt_pit --profiles-dir .

dbt-build:
	$(DBT) build --project-dir dbt_pit --profiles-dir .

dbt-docs:
	$(DBT) docs generate --project-dir dbt_pit --profiles-dir .
	$(DBT) docs serve --project-dir dbt_pit --profiles-dir .

dashboard:
	.venv/Scripts/streamlit.exe run dashboard/app.py

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	.venv/Scripts/ruff.exe check src/ dashboard/ tests/
	.venv/Scripts/ruff.exe format --check src/ dashboard/ tests/

all: ingest build export benchmark dbt-build
	@echo ""
	@echo "Pipeline complete. Run 'make dashboard' to view the result."

clean:
	@echo "Removing .venv, dbt_pit/target, dbt_pit/logs, __pycache__..."
