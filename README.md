# Property Management Analytics

[![Open Financial Dashboard](https://img.shields.io/badge/Open-Financial%20Dashboard-ff4b4b?style=for-the-badge)](https://pma-financial-dashboard.streamlit.app/)
[![Open Leasing Dashboard](https://img.shields.io/badge/Open-Leasing%20Dashboard-ff4b4b?style=for-the-badge)](https://pma-leasing-dashboard.streamlit.app/)
[![Open Operations Dashboard](https://img.shields.io/badge/Open-Operations%20Dashboard-ff4b4b?style=for-the-badge)](https://pma-operations-dashboard.streamlit.app/)

Three connected but analytically distinct products for a conventional multifamily
portfolio:

1. **Financial Performance & Asset Health** — where financial performance is weak and
   which revenue or expense categories warrant review.
2. **Leasing, Occupancy & Revenue Risk** — which future lease events and tenant balances
   require action.
3. **Property Operations & Maintenance** — where workload, service performance,
   recurring issues, or vendor patterns require intervention.

> This is an independent portfolio project. Operational records are synthetic. The
> repository does not use or reproduce proprietary schemas or production data.

## Architecture

Python generates a deterministic portfolio in DuckDB, dbt applies the governed
`source -> stg -> base -> int -> dim/rpt` transformation flow, and three
Streamlit/Plotly entrypoints serve the decision workflows.
The checked-in DuckDB artifact lets hosted apps start without generating data at runtime.

See [architecture](docs/architecture.md) to learn more.

## Dataset

- Cutoff: June 30, 2026; history begins July 1, 2023.
- 24 properties in four U.S. metros, 3,016 units, and two property classes.
- Lease events extend through June 2027 for a twelve-month action horizon.
- Financial transactions, budgets, tenant subledger activity, work orders, status
  history, and vendor costs are deterministic synthetic data.
- HUD FY2026 county-level Fair Market Rent is included only as a public policy benchmark,
  not an asking-rent or valuation benchmark.
- Seven planted raw data-quality issues are documented in the raw-data ERD and cleaned in dbt
  handling.

## Run locally

Python 3.12 and `uv` are required.

```bash
make install
make build
make test
```

Run each product independently:

```bash
make run-financial
make run-leasing
make run-operations
```

The apps read `data/warehouse.duckdb` in read-only mode. Override it with
`PMA_WAREHOUSE_PATH`. Cross-app deep links can be configured with
`PMA_FINANCIAL_APP_URL`, `PMA_LEASING_APP_URL`, and `PMA_OPERATIONS_APP_URL`.

## Quality gates

`make test` regenerates the fixed-seed portfolio, builds every dbt model and test, then
runs Python and Streamlit application tests. `make lint` checks Python, SQL, model
naming, dbt lineage boundaries, and deterministic SQL. CI also parses the project and
generates dbt documentation from the completed build.

Financial release checks include balanced journals, AR and allocation reconciliation,
and portfolio-to-property aggregation. Cross-product checks ensure contextual metrics
come from the owning domain rather than being independently recalculated.

## Limitations

- This is a static portfolio artifact, not a live operational system.
- Forecast views are explicitly labeled scenarios or signed-lease commitments, not
  machine-learning predictions.
- Analysis identifies signals, arithmetic contributors, and associations; it does not
  claim unsupported causation.
- The multifamily model does not cover commercial, student, senior, or mixed-use lease
  semantics.
