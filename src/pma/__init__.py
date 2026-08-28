"""Property management analytics portfolio package."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE_PATH = PROJECT_ROOT / "data" / "warehouse.duckdb"

