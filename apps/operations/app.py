"""Property Operations & Maintenance Performance decision application."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from pma.app_shared import (
    format_metric,
    metric_card,
    render_domain_navigation,
    render_empty_state,
    section_header,
    sidebar_filters,
    style_chart,
)
from pma.data_access import load_query

APP_TITLE = "Property Operations & Maintenance Performance"
CUTOFF_DATE = date(2026, 6, 30)

st.set_page_config(page_title=APP_TITLE, page_icon="🛠️", layout="wide")
st.title(APP_TITLE)
st.caption(
    "Where are operational problems occurring, and how efficiently are they being addressed?"
)


def load_frame(sql: str, columns: tuple[str, ...] = ()) -> pd.DataFrame:
    """Load an app relation and retain a user-safe error for the shared empty state."""

    result = load_query(sql, columns=columns)
    if not result.available:
        st.session_state.setdefault("operations_load_errors", []).append(result.error)
    return result.data


properties = load_frame(
    "select property_id, property_name, market_id, property_class "
    "from main_core.dim_property__current order by property_name",
    ("property_id", "property_name"),
)
if properties.empty:
    render_empty_state(
        "Operations data is unavailable",
        detail="Build the warehouse and operations marts, then reload this application.",
        error=True,
    )
    st.stop()

deep_link_property = st.query_params.get("property_id")
selection = sidebar_filters(
    properties,
    as_of_date=CUTOFF_DATE,
    min_date=CUTOFF_DATE,
    max_date=CUTOFF_DATE,
    default_property_id=deep_link_property,
)
selected_property_ids = set(selection.property_ids)


def property_scope(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or not selected_property_ids or "property_id" not in frame:
        return frame.copy()
    return frame[frame["property_id"].isin(selected_property_ids)].copy()


monthly = property_scope(
    load_frame("select * from main_operations.rpt_operations_property__monthly")
)
backlog = property_scope(
    load_frame("select * from main_operations.rpt_operations_backlog__monthly")
)
queue = property_scope(load_frame("select * from main_operations.rpt_operations_action__queue"))
categories = property_scope(
    load_frame("select * from main_operations.rpt_operations_category__monthly")
)
recurring = property_scope(
    load_frame("select * from main_operations.rpt_operations_issue__recurring")
)
cost_drivers = property_scope(
    load_frame("select * from main_operations.rpt_operations_cost__drivers_monthly")
)
vendors = load_frame("select * from main_operations.rpt_operations_vendor__scorecard")

for frame in (monthly, backlog, categories, cost_drivers):
    for column in ("month_start_date", "month_end_date"):
        if column in frame:
            frame[column] = pd.to_datetime(frame[column])

if monthly.empty:
    render_empty_state(
        "No operations activity for this selection",
        detail="Clear the property filter or rebuild the operations marts.",
    )
    st.stop()

latest_month = monthly["month_start_date"].max()
latest = monthly[monthly["month_start_date"] == latest_month].copy()
latest_backlog = backlog[backlog["month_start_date"] == latest_month].copy()

work_order_count = int(latest["work_order_count"].sum())
active_units = int(latest["active_rentable_units"].sum())
workload_per_100 = 100.0 * work_order_count / active_units if active_units else None
resolution_eligible = int(latest["resolution_sla_eligible_count"].sum())
resolution_met = int(latest["resolution_sla_met_count"].sum())
resolution_sla_pct = 100.0 * resolution_met / resolution_eligible if resolution_eligible else None
reactive_pct = (
    100.0 * latest["reactive_count"].sum() / work_order_count if work_order_count else None
)
cost_per_unit = latest["total_maintenance_cost"].sum() / active_units if active_units else None

st.subheader("Operations decision summary")
summary_columns = st.columns(5)
with summary_columns[0]:
    metric_card("June work orders", format_metric(work_order_count, kind="integer"))
with summary_columns[1]:
    metric_card("Work orders / 100 units", format_metric(workload_per_100))
with summary_columns[2]:
    metric_card("Open backlog", format_metric(len(queue), kind="integer"))
with summary_columns[3]:
    metric_card("Resolution SLA", format_metric(resolution_sla_pct, kind="percent"))
with summary_columns[4]:
    metric_card("Cost / active unit", format_metric(cost_per_unit, kind="currency"))

tab_priority, tab_trends, tab_cost, tab_recurring, tab_vendor = st.tabs(
    ["Priority & service", "Workload & categories", "Cost & mix", "Recurrence", "Vendors"]
)

with tab_priority:
    section_header(
        "Priority service action",
        decision="Where are backlog and service performance unusual?",
        action="Escalate breached high-priority work and reallocate capacity.",
    )
    property_service = latest[
        [
            "property_id",
            "property_name",
            "work_orders_per_100_units",
            "average_resolution_hours",
            "resolution_sla_compliance_pct",
        ]
    ].merge(
        latest_backlog[
            [
                "property_id",
                "backlog_count",
                "breached_backlog_count",
                "average_backlog_age_days",
                "backlog_month_over_month_change",
            ]
        ],
        on="property_id",
        how="left",
    )
    property_service = property_service.sort_values(
        ["breached_backlog_count", "work_orders_per_100_units"], ascending=False
    )
    st.dataframe(property_service, width="stretch", hide_index=True)

    if queue.empty:
        render_empty_state("No open work orders at the analytics cutoff")
    else:
        st.markdown("#### Work orders requiring action")
        queue_view = queue.sort_values(
            ["priority_weight", "open_age_hours"], ascending=False
        )[
            [
                "work_order_id",
                "property_name",
                "unit_number",
                "priority",
                "category",
                "latest_status",
                "open_age_days",
                "recommended_action",
            ]
        ]
        st.dataframe(queue_view, width="stretch", hide_index=True)

with tab_trends:
    section_header(
        "Normalized workload and category trend",
        decision="Which properties and categories show increasing maintenance demand?",
        action="Review staffing or investigate the fastest-growing material category.",
    )
    portfolio_month = (
        monthly.groupby("month_start_date", as_index=False)
        .agg(
            work_order_count=("work_order_count", "sum"),
            active_units=("active_rentable_units", "sum"),
        )
    )
    portfolio_month["work_orders_per_100_units"] = (
        100.0 * portfolio_month["work_order_count"] / portfolio_month["active_units"]
    )
    workload_figure = px.line(
        portfolio_month,
        x="month_start_date",
        y="work_orders_per_100_units",
        markers=True,
    )
    st.plotly_chart(
        style_chart(workload_figure, title="Monthly work orders per 100 active units"),
        width="stretch",
    )

    latest_category_month = categories["month_start_date"].max()
    category_latest = (
        categories[categories["month_start_date"] == latest_category_month]
        .groupby("category", as_index=False)
        .agg(
            work_order_count=("work_order_count", "sum"),
            month_over_month_change=("work_order_month_over_month_change", "sum"),
            total_cost=("total_cost", "sum"),
        )
        .sort_values("month_over_month_change", ascending=False)
    )
    category_figure = px.bar(
        category_latest,
        x="category",
        y="month_over_month_change",
        color="month_over_month_change",
        color_continuous_scale="RdYlGn_r",
    )
    st.plotly_chart(
        style_chart(category_figure, title="Latest category volume change vs prior month"),
        width="stretch",
    )
    st.caption(
        "Changes identify categories for investigation; they do not demonstrate what caused demand."
    )

with tab_cost:
    section_header(
        "Cost contribution and maintenance mix",
        decision="Is cost pressure associated with volume, severity mix, or cost per order?",
        action="Choose a workload, triage, cost-control, or preventive-scheduling response.",
    )
    cost_outliers = latest.sort_values("cost_per_active_unit", ascending=False)[
        [
            "property_name",
            "active_rentable_units",
            "total_maintenance_cost",
            "cost_per_active_unit",
            "cost_per_work_order",
            "reactive_work_order_pct",
        ]
    ]
    cost_figure = px.bar(
        cost_outliers,
        x="property_name",
        y="cost_per_active_unit",
        color="reactive_work_order_pct",
        labels={"reactive_work_order_pct": "Reactive %"},
    )
    st.plotly_chart(
        style_chart(cost_figure, title="Maintenance cost per active unit", currency_y=True),
        width="stretch",
    )

    latest_driver_month = cost_drivers["month_start_date"].max()
    driver_latest = cost_drivers[cost_drivers["month_start_date"] == latest_driver_month].copy()
    driver_latest = driver_latest.sort_values(
        "total_cost_change", key=lambda values: values.abs(), ascending=False
    )
    st.dataframe(
        driver_latest[
            [
                "property_name",
                "total_cost_change",
                "volume_cost_effect",
                "severity_mix_cost_effect",
                "unit_cost_effect",
                "primary_cost_driver",
            ]
        ],
        width="stretch",
        hide_index=True,
    )

    reactive_month = monthly.groupby("month_start_date", as_index=False).agg(
        reactive_count=("reactive_count", "sum"), work_order_count=("work_order_count", "sum")
    )
    reactive_month["reactive_pct"] = (
        100.0 * reactive_month["reactive_count"] / reactive_month["work_order_count"]
    )
    reactive_figure = px.line(
        reactive_month, x="month_start_date", y="reactive_pct", markers=True
    )
    st.plotly_chart(
        style_chart(reactive_figure, title="Reactive share of work orders", percent_y=True),
        width="stretch",
    )
    st.caption(
        f"Current reactive share is {format_metric(reactive_pct, kind='percent')}. "
        "The app reports mix; it does not impose an external target."
    )

with tab_recurring:
    section_header(
        "Recurring unit/category issues",
        decision="Which repeated issues suggest a larger property or equipment problem?",
        action="Open an asset-level root-cause investigation using the linked prior work order.",
    )
    if recurring.empty:
        render_empty_state("No 90-day recurring unit/category issues in this selection")
    else:
        recurrence_summary = (
            recurring.groupby(["property_name", "category"], as_index=False)
            .agg(
                recurring_orders=("work_order_id", "count"),
                affected_units=("unit_id", "nunique"),
                recurring_cost=("total_cost", "sum"),
            )
            .sort_values(["recurring_orders", "recurring_cost"], ascending=False)
        )
        st.dataframe(recurrence_summary, width="stretch", hide_index=True)
        with st.expander("Recurring work-order evidence", expanded=True):
            st.dataframe(
                recurring[
                    [
                        "work_order_id",
                        "prior_work_order_id",
                        "property_name",
                        "unit_number",
                        "category",
                        "days_since_prior_close",
                        "total_cost",
                    ]
                ],
                width="stretch",
                hide_index=True,
            )
        st.caption(
            "A recurrence is an association requiring investigation; it is not evidence "
            "that a vendor or prior repair caused the repeat."
        )

with tab_vendor:
    section_header(
        "Comparable vendor performance",
        decision="Which vendors show unusual cost or service within comparable work?",
        action="Review assignment or contract performance only where sample gates pass.",
    )
    comparable_vendors = vendors[vendors["comparison_status"] == "comparable"].copy()
    if comparable_vendors.empty:
        render_empty_state(
            "No vendor cohorts meet comparison gates",
            detail=(
                "A vendor needs at least 20 completed orders within category and priority, "
                "with at least two eligible vendors."
            ),
        )
    else:
        vendor_figure = px.scatter(
            comparable_vendors,
            x="cost_per_order_delta",
            y="resolution_hours_delta",
            color="category",
            size="comparable_completed_count",
            hover_name="vendor_name",
            hover_data=["priority", "resolution_sla_compliance_pct"],
        )
        vendor_figure.add_hline(y=0, line_dash="dot", line_color="#64748B")
        vendor_figure.add_vline(x=0, line_dash="dot", line_color="#64748B")
        styled_vendor_figure = style_chart(
            vendor_figure, title="Vendor deltas vs category/priority peers"
        )
        styled_vendor_figure.update_layout(
            legend={"x": 1, "xanchor": "right"}
        )
        st.plotly_chart(styled_vendor_figure, width="stretch")
        st.dataframe(
            comparable_vendors.sort_values(
                ["cost_per_order_delta", "resolution_hours_delta"], ascending=False
            )[
                [
                    "vendor_name",
                    "category",
                    "priority",
                    "comparable_completed_count",
                    "average_cost_per_order",
                    "cost_per_order_delta",
                    "average_resolution_hours",
                    "resolution_hours_delta",
                    "resolution_sla_compliance_pct",
                ]
            ],
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "Peer deltas control for category and priority. They are review signals, "
            "not causal vendor rankings."
        )

render_domain_navigation(
    current_domain="operations",
    property_id=next(iter(selected_property_ids), None),
    as_of_date=CUTOFF_DATE,
)
