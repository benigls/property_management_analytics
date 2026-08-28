"""Tests for the deterministic synthetic raw warehouse."""

from __future__ import annotations

from datetime import date

import duckdb

from pma.generate import generate_warehouse


def _connect(path):
    return duckdb.connect(str(path), read_only=True)


def test_generator_is_reproducible(tmp_path):
    first = tmp_path / "first.duckdb"
    second = tmp_path / "second.duckdb"
    generate_warehouse(first, seed=99, as_of=date(2026, 6, 30))
    generate_warehouse(second, seed=99, as_of=date(2026, 6, 30))
    with _connect(first) as left, _connect(second) as right:
        for table, key in (
            ("properties", "property_id"),
            ("leases", "lease_id"),
            ("charges", "charge_id, source_record_id"),
            ("work_orders", "work_order_id"),
            ("gl_entries", "gl_entry_id"),
        ):
            left_rows = left.execute(f"SELECT * FROM raw.{table} ORDER BY {key}").fetchall()
            right_rows = right.execute(f"SELECT * FROM raw.{table} ORDER BY {key}").fetchall()
            assert left_rows == right_rows


def test_expected_scale_provenance_and_horizon(tmp_path):
    warehouse = tmp_path / "portfolio.duckdb"
    counts = generate_warehouse(warehouse)
    assert counts["properties"] == 24
    assert 2_900 <= counts["units"] <= 3_100
    assert counts["charges"] > 90_000
    assert counts["work_orders"] > 4_000
    with _connect(warehouse) as connection:
        property_cohorts = connection.execute("""
            SELECT market_id, property_class, count(*)
            FROM raw.properties GROUP BY ALL ORDER BY 1, 2
        """).fetchall()
        assert property_cohorts == [
            ("ATL", "A", 3),
            ("ATL", "B", 3),
            ("DFW", "A", 3),
            ("DFW", "B", 3),
            ("PHX", "A", 3),
            ("PHX", "B", 3),
            ("TPA", "A", 3),
            ("TPA", "B", 3),
        ]
        assert connection.execute("SELECT max(lease_end_date) FROM raw.leases").fetchone()[
            0
        ] >= date(2027, 6, 1)
        assert connection.execute(
            "SELECT min(due_date), max(due_date) FROM raw.charges"
        ).fetchone() == (date(2023, 7, 1), date(2026, 6, 1))
        public, synthetic = connection.execute("""
            SELECT count(*) FILTER (WHERE NOT is_synthetic),
                   count(*) FILTER (WHERE is_synthetic)
            FROM raw.hud_fmr
        """).fetchone()
        assert public == 16
        assert synthetic == 0


def test_valid_relationships_and_balanced_journals(tmp_path):
    warehouse = tmp_path / "relationships.duckdb"
    generate_warehouse(warehouse)
    with _connect(warehouse) as connection:
        assert (
            connection.execute("""
            SELECT count(*) FROM raw.units u
            LEFT JOIN raw.properties p USING (property_id)
            WHERE p.property_id IS NULL
        """).fetchone()[0]
            == 0
        )
        assert (
            connection.execute("""
            SELECT count(*) FROM raw.leases l
            LEFT JOIN raw.units u USING (unit_id)
            LEFT JOIN raw.tenants t USING (tenant_id)
            WHERE l.lease_id NOT IN ('DQ-LEASE-OVERLAP-001', 'DQ-LEASE-DATES-001')
              AND (u.unit_id IS NULL OR t.tenant_id IS NULL)
        """).fetchone()[0]
            == 0
        )
        assert (
            connection.execute("""
            SELECT count(*) FROM raw.payment_allocations a
            LEFT JOIN raw.payments p USING (payment_id)
            LEFT JOIN raw.charges c USING (charge_id)
            WHERE a.payment_allocation_id <> 'DQ-ALLOC-ORPHAN-001'
              AND (p.payment_id IS NULL OR c.charge_id IS NULL)
        """).fetchone()[0]
            == 0
        )
        assert (
            connection.execute("""
            SELECT count(*) FROM (
                SELECT journal_id, sum(debit_amount) debit, sum(credit_amount) credit
                FROM raw.gl_entries GROUP BY journal_id
            ) WHERE debit <> credit
        """).fetchone()[0]
            == 0
        )
        revenue_reconciliation = connection.execute("""
            WITH deduplicated_charges AS (
              SELECT charge_id, max(amount - approved_credit_amount) net_amount
              FROM raw.charges GROUP BY charge_id
            )
            SELECT
              (SELECT sum(net_amount) FROM deduplicated_charges),
              (SELECT sum(credit_amount) FROM raw.gl_entries
               WHERE account_code IN ('REV_RENT', 'REV_OTHER'))
        """).fetchone()
        assert revenue_reconciliation[0] == revenue_reconciliation[1]

        cash_reconciliation = connection.execute("""
            SELECT
              (SELECT sum(amount) FROM raw.payments WHERE status = 'posted'),
              (SELECT sum(debit_amount) FROM raw.gl_entries
               WHERE account_code = 'ASSET_CASH')
        """).fetchone()
        assert cash_reconciliation[0] == cash_reconciliation[1]


def test_known_quality_defects_are_embedded_in_raw_tables(tmp_path):
    warehouse = tmp_path / "raw-quality.duckdb"
    generate_warehouse(warehouse)
    with _connect(warehouse) as connection:
        assert connection.execute(
            "SELECT count(*) FROM raw.charges WHERE charge_id = 'CHG-0000101'"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT count(*) FROM raw.leases WHERE lease_id = 'DQ-LEASE-OVERLAP-001'"
        ).fetchone()[0] == 1
        assert connection.execute(
            """
            SELECT count(*) FROM raw.leases
            WHERE lease_id = 'DQ-LEASE-DATES-001'
              AND lease_end_date < lease_start_date
            """
        ).fetchone()[0] == 1
        assert connection.execute(
            """
            SELECT count(*) FROM raw.payment_allocations
            WHERE payment_allocation_id = 'DQ-ALLOC-ORPHAN-001'
              AND charge_id = 'CHG-NOT-FOUND'
            """
        ).fetchone()[0] == 1
        assert connection.execute(
            """
            SELECT count(*) FROM raw.gl_entries
            WHERE journal_id = 'DQ-J-INACTIVE-001'
            """
        ).fetchone()[0] == 2
        assert connection.execute(
            """
            SELECT count(*) FROM raw.work_orders
            WHERE category = 'Plumbing' AND vendor_id IS NULL
            """
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT count(*) FROM raw.raw_data_quality_issues"
        ).fetchone()[0] == 0
