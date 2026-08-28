"""Validate repeatable dbt outputs in isolated DuckDB warehouses."""

from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import duckdb

from pma import PROJECT_ROOT
from pma.generate import DEFAULT_AS_OF, DEFAULT_SEED, generate_warehouse

REPORT_KEYS = {
    "main_operations.rpt_operations_backlog__monthly": ("property_id", "month_start_date"),
    "main_operations.rpt_operations_cost__drivers_monthly": ("property_id", "month_start_date"),
    "main_operations.rpt_operations_vendor__scorecard": ("vendor_id", "category", "priority"),
}
FLOAT_TYPES = {"FLOAT", "REAL", "DOUBLE"}


def compare_reports(
    baseline: Path, candidate: Path, tolerance: float = 1e-9
) -> dict[str, dict[str, float]]:
    """Compare report contracts exactly except for explicitly typed floating values."""

    differences: dict[str, dict[str, float]] = {}
    with (
        duckdb.connect(str(baseline), read_only=True) as left,
        duckdb.connect(str(candidate), read_only=True) as right,
    ):
        for relation, keys in REPORT_KEYS.items():
            left_schema = left.execute(f"describe {relation}").fetchall()
            right_schema = right.execute(f"describe {relation}").fetchall()
            if left_schema != right_schema:
                raise AssertionError(f"{relation}: schema changed")

            columns = [row[0] for row in left_schema]
            types = {row[0]: row[1].split("(", 1)[0].upper() for row in left_schema}
            order_by = ", ".join(keys)
            left_rows = left.execute(f"select * from {relation} order by {order_by}").fetchall()
            right_rows = right.execute(f"select * from {relation} order by {order_by}").fetchall()
            if len(left_rows) != len(right_rows):
                raise AssertionError(
                    f"{relation}: row count changed from {len(left_rows)} to {len(right_rows)}"
                )

            max_differences: dict[str, float] = {}
            for row_number, (left_row, right_row) in enumerate(
                zip(left_rows, right_rows, strict=True), start=1
            ):
                for column, left_value, right_value in zip(
                    columns, left_row, right_row, strict=True
                ):
                    is_float_pair = (
                        types[column] in FLOAT_TYPES
                        and left_value is not None
                        and right_value is not None
                    )
                    if is_float_pair:
                        delta = abs(float(left_value) - float(right_value))
                        max_differences[column] = max(max_differences.get(column, 0.0), delta)
                        if not math.isclose(
                            float(left_value), float(right_value), rel_tol=0.0, abs_tol=tolerance
                        ):
                            raise AssertionError(
                                f"{relation} row {row_number} column {column}: "
                                f"difference {delta} exceeds {tolerance}"
                            )
                    elif left_value != right_value:
                        raise AssertionError(
                            f"{relation} row {row_number} column {column}: exact value changed"
                        )
            differences[relation] = max_differences
    return differences


def _dbt_build(warehouse: Path, as_of: date) -> None:
    environment = os.environ.copy()
    environment["PMA_WAREHOUSE_PATH"] = str(warehouse)
    command = [
        sys.executable,
        "-m",
        "dbt.cli.main",
        "build",
        "--quiet",
        "--project-dir",
        str(PROJECT_ROOT / "analytics"),
        "--profiles-dir",
        str(PROJECT_ROOT / "analytics"),
        "--target",
        "ci",
        "--vars",
        f'{{"as_of_date":"{as_of.isoformat()}"}}',
    ]
    subprocess.run(command, check=True, env=environment, cwd=PROJECT_ROOT)


def validate_builds(as_of: date, seed: int, tolerance: float) -> None:
    """Compare a same-target rerun and a fresh-target build."""

    with tempfile.TemporaryDirectory(prefix="pma-determinism-") as directory:
        root = Path(directory)
        working = root / "working.duckdb"
        baseline = root / "baseline.duckdb"
        fresh = root / "fresh.duckdb"

        generate_warehouse(working, seed=seed, as_of=as_of)
        _dbt_build(working, as_of)
        shutil.copy2(working, baseline)
        _dbt_build(working, as_of)
        rerun = compare_reports(baseline, working, tolerance)

        generate_warehouse(fresh, seed=seed, as_of=as_of)
        _dbt_build(fresh, as_of)
        fresh_result = compare_reports(baseline, fresh, tolerance)

        for label, result in (("same-target", rerun), ("fresh-target", fresh_result)):
            maximum = max(
                (value for report in result.values() for value in report.values()), default=0
            )
            print(f"{label}: deterministic (maximum floating difference={maximum:.3g})")


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected ISO date YYYY-MM-DD") from error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=_parse_date, default=DEFAULT_AS_OF)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--tolerance", type=float, default=1e-9)
    arguments = parser.parse_args()
    validate_builds(arguments.as_of, arguments.seed, arguments.tolerance)


if __name__ == "__main__":
    main()
