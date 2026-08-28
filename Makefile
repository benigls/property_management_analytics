.PHONY: install generate dbt-deps build test lint dbt-parse dbt-docs dbt-docs-serve determinism run-financial run-leasing run-operations

AS_OF_DATE ?= 2026-06-30
DBT_TARGET ?= dev
PMA_WAREHOUSE_PATH ?= data/warehouse.duckdb
export PMA_WAREHOUSE_PATH
DBT_ARGS = --project-dir analytics --profiles-dir analytics --target $(DBT_TARGET) --vars '{"as_of_date":"$(AS_OF_DATE)"}'

install:
	uv sync --all-groups

generate:
	uv run pma-generate --output "$(PMA_WAREHOUSE_PATH)" --seed 20260828 --as-of $(AS_OF_DATE)

dbt-deps:
	uv run dbt deps --project-dir analytics --profiles-dir analytics

build: generate dbt-deps
	uv run dbt build $(DBT_ARGS)

test: build
	uv run pytest

lint:
	uv run ruff check src tests apps
	uv run sqlfluff lint analytics/models

dbt-parse: dbt-deps
	uv run dbt parse $(DBT_ARGS)

dbt-docs: build
	uv run dbt docs generate $(DBT_ARGS)

dbt-docs-serve: dbt-docs
	uv run dbt docs serve $(DBT_ARGS)

determinism:
	uv run pma-validate-determinism --as-of $(AS_OF_DATE)

run-financial:
	uv run streamlit run apps/financial/app.py

run-leasing:
	uv run streamlit run apps/leasing/app.py

run-operations:
	uv run streamlit run apps/operations/app.py
