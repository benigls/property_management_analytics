"""Operations mart contracts and Streamlit application tests."""

from pathlib import Path

import duckdb
from streamlit.testing.v1 import AppTest

from pma.data_access import resolve_warehouse_path

APP_PATH = Path(__file__).parents[1] / "apps" / "operations" / "app.py"


def _run_app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=30).run()


def test_operations_marts_enforce_event_and_comparison_contracts() -> None:
    with duckdb.connect(str(resolve_warehouse_path()), read_only=True) as connection:
        relations = {
            row[0]
            for row in connection.execute("""
                select table_name
                from information_schema.tables
                where table_schema = 'main_operations'
            """).fetchall()
        }
        assert {
            "int_work_order__performance",
            "rpt_operations_property__monthly",
            "rpt_operations_backlog__monthly",
            "rpt_operations_action__queue",
            "rpt_operations_issue__recurring",
            "rpt_operations_cost__drivers_monthly",
            "rpt_operations_vendor__scorecard",
        } <= relations

        reopened = connection.execute("""
            select reopen_count, valid_closed_at, resolution_hours
            from main_operations.int_work_order__performance
            where work_order_id = 'WO-000001'
        """).fetchone()
        assert reopened[0] == 1
        assert str(reopened[1]) == "2023-07-13 16:00:00"
        assert reopened[2] == 272.0

        backlog_count = connection.execute("""
            select sum(backlog_count)
            from main_operations.rpt_operations_backlog__monthly
            where month_start_date = date '2026-06-01'
        """).fetchone()[0]
        queue_count = connection.execute(
            "select count(*) from main_operations.rpt_operations_action__queue"
        ).fetchone()[0]
        assert backlog_count == queue_count == 10

        max_residual = connection.execute("""
            select max(abs(decomposition_residual))
            from main_operations.rpt_operations_cost__drivers_monthly
            where prior_total_maintenance_cost is not null
        """).fetchone()[0]
        assert max_residual < 0.01

        invalid_comparisons = connection.execute("""
            select count(*)
            from main_operations.rpt_operations_vendor__scorecard
            where comparison_status = 'comparable'
              and (comparable_completed_count < 20 or eligible_vendor_count < 2)
        """).fetchone()[0]
        assert invalid_comparisons == 0

        planted_recurrence = connection.execute("""
            select count(*)
            from main_operations.rpt_operations_issue__recurring
            where property_id = 'ATL-B02' and category = 'hvac'
        """).fetchone()[0]
        assert planted_recurrence == 8

        planted_backlog = connection.execute("""
            select backlog_count, breached_backlog_count, backlog_month_over_month_change
            from main_operations.rpt_operations_backlog__monthly
            where property_id = 'DFW-A03' and month_start_date = date '2026-06-01'
        """).fetchone()
        assert planted_backlog[0] >= 8
        assert planted_backlog[1] >= 8
        assert planted_backlog[2] > 0

        planted_vendor = connection.execute("""
            select comparison_status, cost_per_order_delta, resolution_hours_delta
            from main_operations.rpt_operations_vendor__scorecard
            where vendor_id = 'VEND-HVAC-03'
              and category = 'hvac'
              and priority = 'normal'
        """).fetchone()
        assert planted_vendor[0] == "comparable"
        assert planted_vendor[1] > 0
        assert planted_vendor[2] > 0


def test_operations_app_starts() -> None:
    app = _run_app()

    assert not app.exception


def test_operations_app_handles_missing_warehouse(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PMA_WAREHOUSE_PATH", str(tmp_path / "missing.duckdb"))
    app = _run_app()

    assert not app.exception
    assert app.warning
    assert any("Build the warehouse" in warning.value for warning in app.warning)
