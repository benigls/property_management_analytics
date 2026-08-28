"""Read-only DuckDB access shared by the three analytics applications.

Application pages should use :func:`load_query` when a missing warehouse or an
optional mart should result in an empty state.  Tests and release checks can use
:func:`query_dataframe` when a query failure must be raised immediately.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import streamlit as st

from pma import WAREHOUSE_PATH

_READ_ONLY_START = re.compile(r"^\s*(select|with|show|describe|explain)\b", re.IGNORECASE)


class DataAccessError(RuntimeError):
    """Raised when an application query cannot be executed safely."""


class WarehouseUnavailableError(DataAccessError):
    """Raised when the configured analytics artifact is not available."""


@dataclass(frozen=True)
class QueryResult:
    """A recoverable application-query result.

    ``error`` is intentionally user-safe and contains no SQL text or parameters.
    Domain apps can pass it to the shared empty-state component while logging
    richer diagnostics separately if needed.
    """

    data: pd.DataFrame
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.error is None

    @property
    def empty(self) -> bool:
        return self.data.empty


def resolve_warehouse_path(database_path: str | PathLike[str] | None = None) -> Path:
    """Resolve an explicit path, environment override, or package default."""

    configured = database_path or os.getenv("PMA_WAREHOUSE_PATH") or WAREHOUSE_PATH
    return Path(configured).expanduser().resolve()


def warehouse_available(database_path: str | PathLike[str] | None = None) -> bool:
    """Return whether the configured DuckDB artifact exists as a regular file."""

    return resolve_warehouse_path(database_path).is_file()


def _validate_read_only_query(sql: str) -> str:
    statement = sql.strip()
    if not statement:
        raise DataAccessError("The analytics query is empty.")
    if not _READ_ONLY_START.match(statement):
        raise DataAccessError("Only read-only analytics queries are allowed.")

    # DuckDB's read-only connection is the final write-protection layer.  This
    # guard also prevents accidentally sending a second statement.
    without_trailing_delimiter = statement[:-1].rstrip() if statement.endswith(";") else statement
    if ";" in without_trailing_delimiter:
        raise DataAccessError("Only one analytics query may be executed at a time.")
    return without_trailing_delimiter


@st.cache_resource(show_spinner=False)
def get_connection(database_path: str) -> duckdb.DuckDBPyConnection:
    """Open and cache a DuckDB connection with filesystem writes disabled."""

    path = resolve_warehouse_path(database_path)
    if not path.is_file():
        raise WarehouseUnavailableError(
            "The analytics warehouse is not available. Build the data artifact and try again."
        )
    try:
        return duckdb.connect(str(path), read_only=True)
    except duckdb.Error as exc:
        raise WarehouseUnavailableError(
            "The analytics warehouse could not be opened in read-only mode."
        ) from exc


@st.cache_data(show_spinner=False, ttl=300)
def _cached_query(
    database_path: str,
    sql: str,
    parameters: tuple[Any, ...],
) -> pd.DataFrame:
    connection = get_connection(database_path)
    try:
        return connection.execute(sql, parameters).fetchdf()
    except duckdb.Error as exc:
        raise DataAccessError("The requested analytics data could not be loaded.") from exc


def query_dataframe(
    sql: str,
    parameters: Sequence[Any] | None = None,
    *,
    database_path: str | PathLike[str] | None = None,
    required_columns: Sequence[str] = (),
) -> pd.DataFrame:
    """Execute one parameterized read query and return a defensive dataframe copy.

    Values must be supplied through ``parameters`` rather than interpolated into
    SQL. Identifier selection remains the caller's responsibility and should be
    selected from a fixed allow-list, never from raw user input.
    """

    statement = _validate_read_only_query(sql)
    path = resolve_warehouse_path(database_path)
    frame = _cached_query(str(path), statement, tuple(parameters or ())).copy()
    missing = set(required_columns) - set(frame.columns)
    if missing:
        raise DataAccessError(
            f"The analytics result is missing required columns: {', '.join(sorted(missing))}."
        )
    return frame


def load_query(
    sql: str,
    parameters: Sequence[Any] | None = None,
    *,
    database_path: str | PathLike[str] | None = None,
    columns: Sequence[str] = (),
) -> QueryResult:
    """Run an app query, converting expected availability failures to empty data."""

    try:
        return QueryResult(
            query_dataframe(
                sql,
                parameters,
                database_path=database_path,
                required_columns=columns,
            )
        )
    except DataAccessError as exc:
        return QueryResult(pd.DataFrame(columns=list(columns)), str(exc))


def clear_query_cache() -> None:
    """Clear cached query results; useful after replacing the warehouse artifact."""

    _cached_query.clear()
