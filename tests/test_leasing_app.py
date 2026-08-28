"""Application and decision-contract tests for the leasing product."""

from pathlib import Path

import duckdb
from streamlit.testing.v1 import AppTest

from pma.data_access import resolve_warehouse_path

APP_PATH = Path(__file__).parents[1] / "apps" / "leasing" / "app.py"


def test_leasing_marts_preserve_decision_contracts() -> None:
    with duckdb.connect(str(resolve_warehouse_path()), read_only=True) as connection:
        relations = {
            row[0]
            for row in connection.execute("""
                select table_name from information_schema.tables
                where table_schema = 'main_leasing'
            """).fetchall()
        }
        assert {
            "rpt_leasing_property__daily_occupancy",
            "rpt_leasing_occupancy__scenario",
            "rpt_leasing_expiration__exposure",
            "rpt_leasing_delinquency__current",
            "rpt_leasing_action__queue",
        } <= relations

        planted_exposure = connection.execute("""
            select count(*)
            from main_leasing.rpt_leasing_expiration__exposure
            where property_id = 'PHX-B02'
              and mitigation_status = 'unmitigated'
              and expiration_date <= date '2026-09-30'
        """).fetchone()[0]
        assert planted_exposure >= 40

        action_types = {
            row[0]
            for row in connection.execute("""
                select distinct action_type
                from main_leasing.rpt_leasing_action__queue
            """).fetchall()
        }
        assert action_types == {"lease_expiration", "tenant_delinquency"}


def test_leasing_app_starts() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    assert not app.exception
