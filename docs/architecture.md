# Architecture and product boundaries

The repository implements three independently deployed analytics products on one
governed DuckDB/dbt foundation. The products share identifiers and validated facts,
but detailed analytical ownership lives in dbt model metadata.

```text
HUD context + deterministic synthetic sources
                    |
                    v
     source -> stg -> int -> dim/rpt
                    |
          +---------+---------+
          |         |         |
          v         v         v
      financial  leasing  operations
       reports    reports    reports
          |         |         |
          v         v         v
       app 1      app 2      app 3
```

The dbt layers are organized in separate model directories:

- `models/staging/` contains one-to-one source extracts.
- `models/intermediate/` contains reusable joins, conformed entities, grain
  changes, and domain helpers.
- `models/marts/core/` contains shared dimensions and reconciliation reports.
- `models/marts/` contains the financial, leasing, and operations application
  outputs.

The intermediate models are physically stored in their own folder even when a
specific high-reuse model explicitly remains in the conformed schema for a
stable downstream storage contract. dbt dependencies always use the canonical
model filename through `ref()`; model aliases are not used.

## Boundaries

- Financial models own accounting outcomes, financial trends, and budget variance.
- Leasing models own occupancy, lease events, vacancy, renewal, and tenant revenue risk.
- Operations models own work-order service, recurring issues, vendors, and maintenance cost drivers.
- Contextual metrics are selected from the owning mart and are never reimplemented downstream.
- Data trust is embedded in each product rather than implemented as a fourth dashboard.

## Provenance

All operational records are deterministic synthetic demonstration data. HUD FY2026
Fair Market Rents are external policy benchmarks. Nothing in this repository represents
a proprietary schema, production export, or claim of hands-on Yardi access.
