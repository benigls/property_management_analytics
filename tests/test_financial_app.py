from pathlib import Path

from streamlit.testing.v1 import AppTest

from pma import PROJECT_ROOT

APP_PATH = PROJECT_ROOT / "apps" / "financial" / "app.py"


def _run_app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=30).run()


def test_financial_app_starts() -> None:
    app = _run_app()

    assert not app.exception


def test_financial_app_handles_missing_warehouse(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PMA_WAREHOUSE_PATH", str(tmp_path / "missing.duckdb"))
    app = _run_app()

    assert not app.exception
    assert app.warning
    assert any("warehouse is not available" in warning.value for warning in app.warning)
