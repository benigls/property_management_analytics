"""Leasing, occupancy, and tenant revenue-risk decision application."""

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

AS_OF_DATE = date(2026, 6, 30)


def _data(sql: str, columns: tuple[str, ...] = ()) -> pd.DataFrame:
    """Load a recoverable leasing-app query."""

    return load_query(sql, columns=columns).data


def _selected(frame: pd.DataFrame, property_ids: tuple[str, ...]) -> pd.DataFrame:
    if frame.empty or not property_ids or "property_id" not in frame:
        return frame
    return frame[frame["property_id"].isin(property_ids)].copy()


st.set_page_config(
    page_title="Leasing, Occupancy & Revenue Risk",
    page_icon="🏠",
    layout="wide",
)
st.title("Leasing, Occupancy & Revenue Risk")
st.caption(
    "Where is future occupancy or rental revenue at risk, and where should the leasing team "
    "act now?"
)

properties_result = load_query(
    """
    select property_id, property_name, market_id, property_class
    from main_core.dim_property__current
    where active_from <= date '2026-06-30'
      and (active_to is null or active_to >= date '2026-06-30')
    order by property_name
    """,
    columns=("property_id", "property_name", "market_id", "property_class"),
)

if not properties_result.available or properties_result.empty:
    render_empty_state(
        "Leasing marts are unavailable",
        detail=properties_result.error or "Build the analytics warehouse and retry.",
        error=True,
    )
    st.stop()

deep_link_property = st.query_params.get("property_id")
selection = sidebar_filters(
    properties_result.data,
    as_of_date=AS_OF_DATE,
    min_date=AS_OF_DATE,
    max_date=AS_OF_DATE,
    default_property_id=deep_link_property,
)
selected_ids = selection.property_ids

queue = _selected(
    _data("select * from main_leasing.rpt_leasing_action__queue order by priority_score desc"),
    selected_ids,
)
exposure = _selected(
    _data("select * from main_leasing.rpt_leasing_expiration__exposure"), selected_ids
)
scenario = _selected(
    _data("select * from main_leasing.rpt_leasing_occupancy__scenario"), selected_ids
)
monthly_occupancy = _selected(
    _data("select * from main_leasing.rpt_leasing_property__monthly_occupancy"), selected_ids
)
renewal = _selected(_data("select * from main_leasing.rpt_leasing_renewal__turnover"), selected_ids)
vacancy = _selected(_data("select * from main_leasing.rpt_leasing_vacancy__episode"), selected_ids)
delinquency = _selected(
    _data("select * from main_leasing.rpt_leasing_delinquency__current"), selected_ids
)

latest_occupancy = (
    monthly_occupancy[pd.to_datetime(monthly_occupancy["month_end_date"]).dt.date == AS_OF_DATE]
    if not monthly_occupancy.empty
    else monthly_occupancy
)
current_occupancy = (
    latest_occupancy["occupied_units"].sum() / latest_occupancy["active_rentable_units"].sum() * 100
    if not latest_occupancy.empty and latest_occupancy["active_rentable_units"].sum()
    else None
)
unmitigated = (
    exposure.loc[
        exposure.get("mitigation_status", pd.Series(dtype=str)) == "unmitigated",
        "unmitigated_rent_exposure",
    ].sum()
    if not exposure.empty
    else 0
)
delinquent_balance = delinquency["outstanding_balance"].sum() if not delinquency.empty else 0

summary_columns = st.columns(4)
with summary_columns[0]:
    metric_card("Physical occupancy", format_metric(current_occupancy, kind="percent"))
with summary_columns[1]:
    metric_card("Unmitigated monthly rent", format_metric(unmitigated, kind="currency", decimals=0))
with summary_columns[2]:
    metric_card(
        "Tenant balance at risk", format_metric(delinquent_balance, kind="currency", decimals=0)
    )
with summary_columns[3]:
    metric_card("Open leasing actions", format_metric(len(queue), kind="integer"))

act_tab, outlook_tab, expiration_tab, history_tab = st.tabs(
    ["Act now", "Occupancy outlook", "Expirations & mitigation", "History & balances"]
)

with act_tab:
    section_header(
        "Prioritized lease and tenant action queue",
        decision="Which exposures require action first?",
        action="Assign renewal, replacement-leasing, or evidence-backed collection outreach.",
    )
    st.caption(
        "Expiration score = contractual monthly rent + $5 × urgency days. Delinquency score "
        "= outstanding rent + $10 × oldest days past due. Rank within action type before "
        "comparing different workflows."
    )
    if queue.empty:
        render_empty_state("No open leasing actions for this selection")
    else:
        display_queue = queue[
            [
                "priority_tier",
                "action_type",
                "property_name",
                "unit_number",
                "tenant_name",
                "action_date",
                "financial_exposure",
                "evidence",
                "recommended_action",
            ]
        ].copy()
        st.dataframe(display_queue, use_container_width=True, hide_index=True)

with outlook_tab:
    section_header(
        "Signed commitment and base occupancy scenario",
        decision="Where could occupancy decline?",
        action="Review signed coverage first, then resource unresolved expirations.",
    )
    st.info(
        "Committed occupancy is signed lease coverage. Base scenario is an estimate that adds "
        "historical renewal and vacancy behavior for unresolved expirations; it is not a promise "
        "or causal forecast.",
        icon="ℹ️",
    )
    if scenario.empty:
        render_empty_state("No occupancy scenario for this selection")
    else:
        scenario_long = scenario.melt(
            id_vars=["property_name", "forecast_month_end"],
            value_vars=["committed_occupancy_pct", "base_scenario_occupancy_pct"],
            var_name="scenario",
            value_name="occupancy_pct",
        )
        figure = px.line(
            scenario_long,
            x="forecast_month_end",
            y="occupancy_pct",
            color="property_name",
            line_dash="scenario",
            markers=True,
        )
        figure.update_layout(showlegend=False)
        st.plotly_chart(
            style_chart(figure, title="12-month occupancy outlook", percent_y=True),
            use_container_width=True,
        )
        st.dataframe(
            scenario[
                [
                    "property_name",
                    "forecast_month_end",
                    "active_rentable_units",
                    "committed_occupancy_pct",
                    "base_scenario_occupancy_pct",
                    "unresolved_expired_units",
                    "base_scenario_method",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

with expiration_tab:
    section_header(
        "Expiration concentration and signed mitigation evidence",
        decision="When, where, and how much rent is exposed?",
        action="Prioritize unmitigated leases and remove signed renewals or replacements.",
    )
    if exposure.empty:
        render_empty_state("No expirations in the 12-month horizon")
    else:
        expiration_summary = exposure.groupby(
            ["expiration_month", "mitigation_status"], as_index=False
        ).agg(
            lease_count=("lease_id", "count"), contractual_rent=("contractual_monthly_rent", "sum")
        )
        figure = px.bar(
            expiration_summary,
            x="expiration_month",
            y="contractual_rent",
            color="mitigation_status",
            hover_data=["lease_count"],
        )
        styled_figure = style_chart(
            figure, title="Contractual rent by expiration month", currency_y=True
        )
        styled_figure.update_layout(
            legend={"orientation": "h", "yanchor": "bottom", "y": 1, "x": 0.75},
            margin={"l": 20, "r": 20, "t": 90, "b": 20},
        )
        st.plotly_chart(styled_figure, use_container_width=True)
        st.dataframe(
            exposure.sort_values(
                ["is_mitigated", "days_to_expiration", "contractual_monthly_rent"]
            )[
                [
                    "property_name",
                    "unit_number",
                    "tenant_name",
                    "lease_id",
                    "expiration_date",
                    "days_to_expiration",
                    "contractual_monthly_rent",
                    "mitigation_status",
                    "successor_lease_id",
                    "successor_signed_date",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

with history_tab:
    section_header(
        "Historical retention, turnover, vacancy, and tenant balances",
        decision="What historical behavior should inform planning?",
        action="Focus retention and lease-up work on adverse property-level outcomes.",
    )
    left, right = st.columns(2)
    with left:
        if renewal.empty:
            render_empty_state("No completed lease outcomes")
        else:
            renewal_summary = renewal.groupby("property_name", as_index=False).agg(
                completed_expirations=("lease_id", "count"),
                renewals=("is_renewal", "sum"),
                turnovers=("is_turnover", "sum"),
            )
            renewal_summary["renewal_rate_pct"] = (
                renewal_summary["renewals"] / renewal_summary["completed_expirations"] * 100
            )
            st.dataframe(renewal_summary, use_container_width=True, hide_index=True)
    with right:
        if vacancy.empty:
            render_empty_state("No completed vacancy episodes")
        else:
            vacancy_summary = (
                vacancy.groupby("property_name", as_index=False)
                .agg(
                    vacancy_episodes=("vacancy_episode_id", "count"),
                    average_vacancy_days=("vacancy_days", "mean"),
                    longest_vacancy_days=("vacancy_days", "max"),
                )
                .sort_values("average_vacancy_days", ascending=False)
            )
            st.dataframe(vacancy_summary, use_container_width=True, hide_index=True)

    section_header(
        "Tenant delinquency evidence",
        decision="Which balances require collection outreach?",
        action="Review charge and allocation evidence before contacting the tenant.",
    )
    if delinquency.empty:
        render_empty_state("No positive tenant balances")
    else:
        aging = delinquency.groupby("aging_bucket", as_index=False).agg(
            outstanding_balance=("outstanding_balance", "sum"), charges=("charge_id", "count")
        )
        figure = px.bar(aging, x="aging_bucket", y="outstanding_balance", hover_data=["charges"])
        st.plotly_chart(
            style_chart(figure, title="Outstanding rent by aging bucket", currency_y=True),
            use_container_width=True,
        )
        with st.expander("Charge and payment-allocation evidence"):
            st.dataframe(
                delinquency.sort_values(["days_past_due", "outstanding_balance"], ascending=False)[
                    [
                        "property_name",
                        "unit_number",
                        "tenant_name",
                        "charge_id",
                        "lease_id",
                        "due_date",
                        "net_charge_amount",
                        "allocated_payment_amount",
                        "outstanding_balance",
                        "days_past_due",
                        "aging_bucket",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

render_domain_navigation(
    current_domain="leasing",
    property_id=selected_ids[0] if len(selected_ids) == 1 else None,
    as_of_date=selection.as_of_date,
)
