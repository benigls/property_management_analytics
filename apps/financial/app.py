"""Financial Performance & Asset Health Streamlit application."""

from __future__ import annotations

from datetime import date
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from pma.app_shared import (
    format_metric,
    metric_card,
    render_domain_navigation,
    render_empty_state,
    section_header,
    sidebar_filters,
    style_chart,
    style_table,
)
from pma.data_access import QueryResult, load_query

APP_TITLE = "Financial Performance & Asset Health"
AS_OF_DATE = date(2026, 6, 30)
HISTORY_START = date(2023, 7, 1)


def _property_filter(
    property_ids: tuple[str, ...], *, alias: str = ""
) -> tuple[str, tuple[Any, ...]]:
    if not property_ids:
        return "", ()
    prefix = f"{alias}." if alias else ""
    placeholders = ", ".join("?" for _ in property_ids)
    return f" and {prefix}property_id in ({placeholders})", property_ids


def _show_query_error(result: QueryResult, label: str) -> None:
    if result.error:
        render_empty_state(
            f"{label} is unavailable",
            detail=result.error,
            error=True,
        )


st.set_page_config(page_title=APP_TITLE, page_icon="💼", layout="wide")
st.title(APP_TITLE)
st.caption(
    "Primary decision: Where is the portfolio financially underperforming, "
    "and what evidence warrants further review?"
)
properties_result = load_query(
    """
    select property_id, property_name, market_id, property_class
    from main_core.dim_property__current
    where active_from <= ? and (active_to is null or active_to >= ?)
    order by property_name
    """,
    [AS_OF_DATE, AS_OF_DATE],
    columns=("property_id", "property_name", "market_id", "property_class"),
)
default_property = st.query_params.get("property_id")
selection = sidebar_filters(
    properties_result.data,
    as_of_date=AS_OF_DATE,
    min_date=HISTORY_START,
    max_date=AS_OF_DATE,
    default_property_id=default_property,
)
property_sql, property_parameters = _property_filter(selection.property_ids)

if properties_result.error:
    _show_query_error(properties_result, "Property filters")

summary = load_query(
    f"""
    select
        sum(operating_revenue) as operating_revenue,
        sum(operating_expense) as operating_expense,
        sum(noi) as noi,
        sum(noi) / nullif(sum(operating_revenue), 0) as noi_margin,
        sum(noi_favorable_variance) as noi_favorable_variance
    from main_financial.rpt_financial_property__monthly
    where performance_month = (
        select max(performance_month)
        from main_financial.rpt_financial_property__monthly
        where performance_month <= date_trunc('month', cast(? as date))
    ) {property_sql}
    """,
    (selection.as_of_date, *property_parameters),
    columns=(
        "operating_revenue",
        "operating_expense",
        "noi",
        "noi_margin",
        "noi_favorable_variance",
    ),
)

if summary.empty:
    _show_query_error(summary, "Financial summary")
    if not summary.error:
        render_empty_state(
            detail="Choose a date or property with posted financial activity."
        )
else:
    current = summary.data.iloc[0]
    columns = st.columns(5)
    with columns[0]:
        metric_card(
            "Operating revenue",
            format_metric(current["operating_revenue"], kind="currency", decimals=0),
        )
    with columns[1]:
        metric_card(
            "Operating expense",
            format_metric(current["operating_expense"], kind="currency", decimals=0),
        )
    with columns[2]:
        metric_card("NOI", format_metric(current["noi"], kind="currency", decimals=0))
    with columns[3]:
        metric_card(
            "NOI margin",
            format_metric(current["noi_margin"] * 100, kind="percent", decimals=1),
        )
    with columns[4]:
        metric_card(
            "NOI vs budget",
            format_metric(
                current["noi_favorable_variance"], kind="currency", decimals=0
            ),
            help_text="Positive is favorable; negative is unfavorable.",
        )

section_header(
    "Financial review queue",
    decision="Prioritize material property review",
    action="Assign the highest-ranked adverse signal to an asset or finance owner.",
)
queue = load_query(
    f"""
    select *
    from main_financial.rpt_financial_action__queue
    where performance_month <= date_trunc('month', cast(? as date)) {property_sql}
    order by review_rank
    """,
    (selection.as_of_date, *property_parameters),
    columns=(
        "review_rank",
        "property_id",
        "property_name",
        "review_priority",
        "review_score",
        "noi",
        "noi_favorable_variance",
        "noi_year_over_year_change",
        "noi_portfolio_contribution",
        "adverse_trend_scope",
        "recommended_action",
    ),
)
if queue.empty:
    _show_query_error(queue, "Financial review queue")
    if not queue.error:
        render_empty_state(
            detail="The queue is available at the current analytics cutoff."
        )
else:
    plot_rows = queue.data.nsmallest(10, "review_rank").sort_values("review_score")
    priority_colors = {"high": "#DC2626", "medium": "#D97706", "monitor": "#2563EB"}
    figure = go.Figure(
        go.Bar(
            x=plot_rows["review_score"],
            y=plot_rows["property_name"],
            orientation="h",
            marker_color=[
                priority_colors[value] for value in plot_rows["review_priority"]
            ],
            customdata=plot_rows[["recommended_action"]],
            hovertemplate="%{y}<br>Review score: %{x:.2f}<br>%{customdata[0]}<extra></extra>",
        )
    )
    st.plotly_chart(
        style_chart(figure, title="Current transparent review score"),
        use_container_width=True,
    )
    queue_table = queue.data[
        [
            "review_rank",
            "property_name",
            "review_priority",
            "noi_favorable_variance",
            "noi_year_over_year_change",
            "noi_portfolio_contribution",
            "adverse_trend_scope",
            "recommended_action",
        ]
    ].rename(
        columns={
            "review_rank": "Rank",
            "property_name": "Property",
            "review_priority": "Priority",
            "noi_favorable_variance": "NOI favorable variance",
            "noi_year_over_year_change": "NOI YoY change",
            "noi_portfolio_contribution": "Portfolio NOI share",
            "adverse_trend_scope": "Observed scope",
            "recommended_action": "Next action",
        }
    )
    st.dataframe(style_table(queue_table, precision=2), use_container_width=True)

trend_tab, variance_tab, peer_tab = st.tabs(
    ["Performance trend", "Budget variance", "Valid peer comparison"]
)
with trend_tab:
    section_header(
        "Performance over time",
        decision="Distinguish persistent change from a single month.",
        action="Investigate persistent or accelerating adverse movement.",
    )

    trends = load_query(
        f"""
        select performance_month, sum(noi) as noi, sum(budget_noi) as budget_noi,
            sum(operating_revenue) as operating_revenue,
            sum(operating_expense) as operating_expense
        from main_financial.rpt_financial_property__monthly
        where performance_month <= date_trunc('month', cast(? as date)) {property_sql}
        group by 1 order by 1
        """,
        (selection.as_of_date, *property_parameters),
        columns=(
            "performance_month",
            "noi",
            "budget_noi",
            "operating_revenue",
            "operating_expense",
        ),
    )
    if trends.empty:
        _show_query_error(trends, "Financial trend")
    else:
        figure = go.Figure()
        figure.add_scatter(
            x=trends.data["performance_month"], y=trends.data["noi"], name="Actual NOI"
        )
        figure.add_scatter(
            x=trends.data["performance_month"],
            y=trends.data["budget_noi"],
            name="Budget NOI",
            line={"dash": "dash"},
        )
        st.plotly_chart(
            style_chart(figure, currency_y=True, title=""), use_container_width=True
        )

with variance_tab:
    section_header(
        "Property budget variance",
        decision="Locate financially significant unfavorable variance",
        action="Assign a property variance investigation; negative is unfavorable.",
    )
    variances = load_query(
        f"""
        select property_name, noi_favorable_variance, revenue_favorable_variance,
            expense_favorable_variance
        from main_financial.rpt_financial_property__monthly
        where performance_month = (
            select max(performance_month) from main_financial.rpt_financial_property__monthly
            where performance_month <= date_trunc('month', cast(? as date))
        ) {property_sql}
        order by noi_favorable_variance
        """,
        (selection.as_of_date, *property_parameters),
        columns=(
            "property_name",
            "noi_favorable_variance",
            "revenue_favorable_variance",
            "expense_favorable_variance",
        ),
    )
    if variances.empty:
        _show_query_error(variances, "Budget variance")
    else:
        figure = go.Figure(
            go.Bar(
                x=variances.data["property_name"],
                y=variances.data["noi_favorable_variance"],
                marker_color=[
                    "#DC2626" if value < 0 else "#0F766E"
                    for value in variances.data["noi_favorable_variance"]
                ],
                hovertemplate="%{x}<br>Favorable NOI variance: $%{y:,.0f}<extra></extra>",
            )
        )
        st.plotly_chart(style_chart(figure, currency_y=True), use_container_width=True)

with peer_tab:
    section_header(
        "Same-market, same-class peers",
        decision="Identify normalized performance outliers",
        action="Review NOI-per-unit gaps only within eligible cohorts of at least three.",
    )
    peers = load_query(
        f"""
        select property_name, market_id, property_class, cohort_size, noi_per_unit,
            peer_average_noi_per_unit, noi_per_unit_vs_peer, cohort_noi_rank
        from main_financial.rpt_financial_peer__performance
        where performance_month = (
            select max(performance_month) from main_financial.rpt_financial_peer__performance
            where performance_month <= date_trunc('month', cast(? as date))
        ) {property_sql}
        order by noi_per_unit_vs_peer
        """,
        (selection.as_of_date, *property_parameters),
        columns=(
            "property_name",
            "market_id",
            "property_class",
            "cohort_size",
            "noi_per_unit",
            "peer_average_noi_per_unit",
            "noi_per_unit_vs_peer",
            "cohort_noi_rank",
        ),
    )
    if peers.empty:
        _show_query_error(peers, "Peer comparison")
    else:
        st.dataframe(style_table(peers.data, precision=2), use_container_width=True)

driver_tab, collection_tab = st.tabs(["Expense drivers", "Property collections"])
with driver_tab:
    section_header(
        "Expense category drivers",
        decision="Locate material categories associated with cost change",
        action="Assign the category for cost review; this is contribution evidence, not causality.",
    )
    drivers = load_query(
        f"""
        select account_name, sum(actual_expense) as actual_expense,
            sum(budget_expense) as budget_expense,
            sum(expense_favorable_variance) as expense_favorable_variance,
            sum(expense_year_over_year_change) as expense_year_over_year_change
        from main_financial.rpt_financial_expense__drivers
        where performance_month = (
            select max(performance_month) from main_financial.rpt_financial_expense__drivers
            where performance_month <= date_trunc('month', cast(? as date))
        ) {property_sql}
        group by 1 order by expense_year_over_year_change desc
        """,
        (selection.as_of_date, *property_parameters),
        columns=(
            "account_name",
            "actual_expense",
            "budget_expense",
            "expense_favorable_variance",
            "expense_year_over_year_change",
        ),
    )
    if drivers.empty:
        _show_query_error(drivers, "Expense drivers")
    else:
        figure = go.Figure(
            go.Bar(
                x=drivers.data["expense_year_over_year_change"],
                y=drivers.data["account_name"],
                orientation="h",
                marker_color="#D97706",
            )
        )
        st.plotly_chart(
            style_chart(figure, currency_y=False, title=""), use_container_width=True
        )
        st.dataframe(style_table(drivers.data, precision=2), use_container_width=True)

with collection_tab:
    section_header(
        "Property-level collection performance",
        decision="Identify collection performance associated with financial pressure",
        action="Review the property summary here; tenant-level delinquency remains leasing-owned.",
    )
    collections = load_query(
        f"""
        select property_name, charges_net_of_credits, allocated_payment_amount,
            outstanding_charge_balance, collection_rate, allocation_cutoff_date
        from main_financial.rpt_financial_collections__monthly
        where performance_month = (
            select max(performance_month) from main_financial.rpt_financial_collections__monthly
            where performance_month <= date_trunc('month', cast(? as date))
        ) {property_sql}
        order by collection_rate, outstanding_charge_balance desc
        """,
        (selection.as_of_date, *property_parameters),
        columns=(
            "property_name",
            "charges_net_of_credits",
            "allocated_payment_amount",
            "outstanding_charge_balance",
            "collection_rate",
            "allocation_cutoff_date",
        ),
    )
    if collections.empty:
        _show_query_error(collections, "Collection performance")
    else:
        display_collections = collections.data.copy()
        display_collections["collection_rate"] = (
            display_collections["collection_rate"] * 100
        )
        st.dataframe(
            style_table(display_collections, precision=2), use_container_width=True
        )

section_header(
    "Source transaction drill-through",
    decision="Trace a displayed amount to conformed source records",
    action="Use journal and source record IDs when assigning a finance investigation.",
)
source_rows = load_query(
    f"""
    select posting_date, property_name, journal_id, account_code, account_name, account_type,
        actual_amount, entry_description, source_system, source_record_id
    from main_financial.rpt_financial_source__entries
    where performance_month = (
        select max(performance_month) from main_financial.rpt_financial_source__entries
        where performance_month <= date_trunc('month', cast(? as date))
    ) {property_sql}
    order by abs(actual_amount) desc, property_name
    limit 250
    """,
    (selection.as_of_date, *property_parameters),
    columns=(
        "posting_date",
        "property_name",
        "journal_id",
        "account_code",
        "account_name",
        "account_type",
        "actual_amount",
        "entry_description",
        "source_system",
        "source_record_id",
    ),
)
if source_rows.empty:
    _show_query_error(source_rows, "Source drill-through")
else:
    st.dataframe(style_table(source_rows.data, precision=2), use_container_width=True)

selected_property = (
    selection.property_ids[0] if len(selection.property_ids) == 1 else None
)
render_domain_navigation(
    current_domain="financial",
    property_id=selected_property,
    as_of_date=selection.as_of_date,
)
