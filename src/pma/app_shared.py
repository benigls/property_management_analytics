"""Shared presentation components for the three decision-oriented apps."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

Domain = Literal["financial", "leasing", "operations"]

DOMAIN_LABELS: dict[Domain, str] = {
    "financial": "Financial Performance & Asset Health",
    "leasing": "Leasing, Occupancy & Revenue Risk",
    "operations": "Property Operations & Maintenance Performance",
}

DOMAIN_URL_ENV: dict[Domain, str] = {
    "financial": "PMA_FINANCIAL_APP_URL",
    "leasing": "PMA_LEASING_APP_URL",
    "operations": "PMA_OPERATIONS_APP_URL",
}

@dataclass(frozen=True)
class FilterSelection:
    """Common property/date selection returned by the shared sidebar."""

    property_ids: tuple[str, ...]
    as_of_date: date


def format_metric(
    value: Any,
    *,
    kind: Literal["currency", "percent", "integer", "number"] = "number",
    decimals: int = 1,
) -> str:
    """Apply consistent compact metric formatting, including missing values."""

    if value is None or pd.isna(value):
        return "—"
    numeric = float(value)
    if kind == "currency":
        sign = "-" if numeric < 0 else ""
        return f"{sign}${abs(numeric):,.{decimals}f}"
    if kind == "percent":
        return f"{numeric:.{decimals}f}%"
    if kind == "integer":
        return f"{numeric:,.0f}"
    return f"{numeric:,.{decimals}f}"


def build_app_url(
    domain: Domain,
    *,
    property_id: str | None = None,
    as_of_date: date | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """Build an environment-configured domain URL with encoded deep-link state."""

    environment = os.environ if environ is None else environ
    setting_name = DOMAIN_URL_ENV[domain]
    base_url = environment.get(setting_name, "").strip()
    if not base_url and environ is None:
        # Community Cloud exposes deployment configuration through st.secrets.
        # Local and container deployments can continue to use environment variables.
        try:
            base_url = str(st.secrets.get(setting_name, "")).strip()
        except (FileNotFoundError, KeyError):
            base_url = ""
    if not base_url:
        return None

    split = urlsplit(base_url)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    if property_id:
        query["property_id"] = property_id
    if as_of_date:
        query["as_of_date"] = str(as_of_date)
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), split.fragment))


def domain_navigation_urls(
    *,
    current_domain: Domain,
    property_id: str | None = None,
    as_of_date: date | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[Domain, str]:
    """Return configured links to other owning apps, preserving shared context."""

    links: dict[Domain, str] = {}
    for domain in DOMAIN_LABELS:
        if domain == current_domain:
            continue
        url = build_app_url(
            domain,
            property_id=property_id,
            as_of_date=as_of_date,
            environ=environ,
        )
        if url:
            links[domain] = url
    return links


def style_chart(
    figure: go.Figure,
    *,
    title: str | None = None,
    percent_y: bool = False,
    currency_y: bool = False,
) -> go.Figure:
    """Apply the portfolio's restrained, accessible chart defaults."""

    layout: dict[str, Any] = {
        "template": "plotly_white",
        "colorway": ["#2563EB", "#0F766E", "#D97706", "#7C3AED", "#DC2626"],
        "font": {"family": "Inter, Arial, sans-serif", "color": "#172033"},
        "hoverlabel": {"namelength": -1},
        "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        "margin": {"l": 20, "r": 20, "t": 60 if title else 30, "b": 20},
    }
    if title:
        layout["title"] = title
    figure.update_layout(**layout)
    figure.update_xaxes(showgrid=False, automargin=True)
    figure.update_yaxes(gridcolor="#E5E7EB", zerolinecolor="#CBD5E1", automargin=True)
    if percent_y:
        figure.update_yaxes(ticksuffix="%")
    if currency_y:
        figure.update_yaxes(tickprefix="$", separatethousands=True)
    return figure


def style_table(frame: pd.DataFrame, *, precision: int = 1) -> pd.io.formats.style.Styler:
    """Apply consistent table formatting without mutating the input frame."""

    return frame.style.format(precision=precision, na_rep="—").hide(axis="index")


def metric_card(
    label: str,
    value: Any,
    *,
    delta: str | None = None,
    help_text: str | None = None,
) -> None:
    """Render a common KPI card."""

    st.metric(label=label, value=value, delta=delta, help=help_text)


def section_header(
    title: str,
    *,
    decision: str | None = None,
    action: str | None = None,
) -> None:
    """Render a section title with optional decision and next-action context."""

    st.subheader(title)
    context = [
        label
        for label in (
            f"Decision: {decision}" if decision else None,
            f"Next action: {action}" if action else None,
        )
        if label
    ]
    if context:
        st.caption(" · ".join(context))


def render_empty_state(
    title: str = "No data for this selection",
    *,
    detail: str | None = None,
    error: bool = False,
) -> None:
    """Render an actionable empty or unavailable state without stopping the app."""

    message = title if not detail else f"{title}\n\n{detail}"
    if error:
        st.warning(message, icon="⚠️")
    else:
        st.info(message, icon="ℹ️")


def render_domain_navigation(
    *,
    current_domain: Domain,
    property_id: str | None = None,
    as_of_date: date | str | None = None,
) -> None:
    """Link to owning apps instead of reproducing their detailed analysis."""

    links = domain_navigation_urls(
        current_domain=current_domain,
        property_id=property_id,
        as_of_date=as_of_date,
    )
    if not links:
        return
    st.caption("Continue the property investigation in another decision area:")
    for domain, url in links.items():
        st.link_button(DOMAIN_LABELS[domain], url, use_container_width=True)


def sidebar_filters(
    properties: pd.DataFrame,
    *,
    as_of_date: date,
    min_date: date | None = None,
    max_date: date | None = None,
    default_property_id: str | None = None,
) -> FilterSelection:
    """Render shared property and cutoff filters.

    ``properties`` must contain ``property_id`` and may include ``property_name``.
    Invalid deep-link defaults are ignored rather than crashing a deployed app.
    """

    required = {"property_id"}
    missing = required - set(properties.columns)
    if missing:
        raise ValueError(f"Property filter is missing columns: {', '.join(sorted(missing))}")

    options = properties.drop_duplicates("property_id").copy()
    options["property_id"] = options["property_id"].astype(str)
    if "property_name" not in options:
        options["property_name"] = options["property_id"]
    labels = dict(zip(options["property_id"], options["property_name"], strict=False))
    property_ids = options["property_id"].tolist()

    default = [default_property_id] if default_property_id in property_ids else []
    selected = st.sidebar.multiselect(
        "Properties",
        property_ids,
        default=default,
        format_func=lambda property_id: labels[property_id],
        placeholder="All properties",
    )
    selected_date = st.sidebar.date_input(
        "As-of date",
        value=as_of_date,
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(selected_date, tuple):
        selected_date = selected_date[0]
    return FilterSelection(tuple(selected), selected_date)
