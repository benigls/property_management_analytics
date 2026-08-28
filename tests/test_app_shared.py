from datetime import date

import duckdb
import pytest

from pma.app_shared import (
    build_app_url,
    domain_navigation_urls,
    format_metric,
)
from pma.data_access import (
    DataAccessError,
    clear_query_cache,
    load_query,
    query_dataframe,
    warehouse_available,
)


def test_metric_formatting_handles_signs_and_missing_values() -> None:
    assert format_metric(1234.56, kind="currency", decimals=0) == "$1,235"
    assert format_metric(-1234.56, kind="currency", decimals=1) == "-$1,234.6"
    assert format_metric(94.25, kind="percent", decimals=1) == "94.2%"
    assert format_metric(1200, kind="integer") == "1,200"
    assert format_metric(None, kind="currency") == "—"
    assert format_metric(float("nan")) == "—"


def test_deep_link_encodes_shared_context_and_preserves_existing_query() -> None:
    environment = {
        "PMA_LEASING_APP_URL": "https://leasing.example/app?embed=true#risk",
        "PMA_OPERATIONS_APP_URL": "https://operations.example/app",
    }
    url = build_app_url(
        "leasing",
        property_id="PHX A/01",
        as_of_date=date(2026, 6, 30),
        environ=environment,
    )
    assert url == (
        "https://leasing.example/app?embed=true&property_id=PHX+A%2F01"
        "&as_of_date=2026-06-30#risk"
    )

    links = domain_navigation_urls(
        current_domain="financial",
        property_id="PHX A/01",
        as_of_date="2026-06-30",
        environ=environment,
    )
    assert set(links) == {"leasing", "operations"}
    assert build_app_url("financial", environ=environment) is None


def test_parameterized_read_only_query_and_required_columns(tmp_path) -> None:
    warehouse = tmp_path / "test.duckdb"
    connection = duckdb.connect(str(warehouse))
    connection.execute("create table property_month(property_id varchar, noi decimal(12, 2))")
    connection.execute("insert into property_month values ('A-01', 125.50), ('B-01', 90.00)")
    connection.close()

    clear_query_cache()
    assert warehouse_available(warehouse)
    result = query_dataframe(
        "select property_id, noi from property_month where property_id = ?;",
        ["A-01"],
        database_path=warehouse,
        required_columns=("property_id", "noi"),
    )
    assert result["property_id"].tolist() == ["A-01"]
    assert float(result.loc[0, "noi"]) == 125.5

    with pytest.raises(DataAccessError, match="missing required columns"):
        query_dataframe(
            "select property_id from property_month",
            database_path=warehouse,
            required_columns=("noi",),
        )


@pytest.mark.parametrize(
    "sql",
    [
        "delete from property_month",
        "select 1; select 2",
        "",
    ],
)
def test_query_helper_rejects_non_read_or_multiple_statements(tmp_path, sql) -> None:
    warehouse = tmp_path / "test.duckdb"
    duckdb.connect(str(warehouse)).close()
    with pytest.raises(DataAccessError):
        query_dataframe(sql, database_path=warehouse)


def test_load_query_returns_typed_empty_state_for_missing_warehouse(tmp_path) -> None:
    result = load_query(
        "select property_id, noi from property_month",
        database_path=tmp_path / "missing.duckdb",
        columns=("property_id", "noi"),
    )
    assert not result.available
    assert result.empty
    assert list(result.data.columns) == ["property_id", "noi"]
    assert "warehouse is not available" in result.error
