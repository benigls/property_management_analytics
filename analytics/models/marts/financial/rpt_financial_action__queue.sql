

with rpt_financial_property__monthly as (
    select * from {{ ref('rpt_financial_property__monthly') }}
),
rpt_financial_peer__performance as (
    select * from {{ ref('rpt_financial_peer__performance') }}
),
rpt_financial_portfolio__contribution as (
    select * from {{ ref('rpt_financial_portfolio__contribution') }}
),
rpt_financial_collections__monthly as (
    select * from {{ ref('rpt_financial_collections__monthly') }}
),

latest_month as (
    select max(performance_month) as performance_month
    from rpt_financial_property__monthly
),
components as (
    select
        f.property_id,
        f.property_name,
        f.market_id,
        f.property_class,
        f.performance_month,
        f.noi,
        f.budget_noi,
        f.noi_favorable_variance,
        f.noi_year_over_year_change,
        f.prior_year_noi,
        f.noi_margin,
        c.collection_rate,
        c.outstanding_charge_balance,
        p.noi_per_unit,
        p.peer_average_noi_per_unit,
        p.noi_per_unit_vs_peer,
        pc.noi_portfolio_contribution,
        pc.unfavorable_variance_contribution,
        pc.adverse_trend_scope,
        greatest(0, -f.noi_favorable_variance) / nullif(abs(f.budget_noi), 0)
            as budget_gap_component,
        greatest(0, -f.noi_year_over_year_change) / nullif(abs(f.prior_year_noi), 0)
            as trend_component,
        greatest(0, 1 - coalesce(c.collection_rate, 1)) as collection_component,
        greatest(0, -p.noi_per_unit_vs_peer) / nullif(abs(p.peer_average_noi_per_unit), 0)
            as peer_component,
        f.source_loaded_at,
    from rpt_financial_property__monthly f
    inner join latest_month lm using (performance_month)
    inner join rpt_financial_peer__performance p
        using (property_id, performance_month)
    inner join rpt_financial_portfolio__contribution pc
        using (property_id, performance_month)
    left join rpt_financial_collections__monthly c
        using (property_id, performance_month)
),
scored as (
    select
        *,
        cast(
            100 * (
                0.35 * coalesce(budget_gap_component, 0)
                + 0.30 * coalesce(trend_component, 0)
                + 0.20 * coalesce(collection_component, 0)
                + 0.15 * coalesce(peer_component, 0)
            ) as decimal(18, 4)
        ) as review_score
    from components
)
, final as (
    select
        *,
        row_number() over (
            order by review_score desc, abs(noi_favorable_variance) desc, property_id
        ) as review_rank,
        case
            when review_score >= 10 then 'high'
            when review_score >= 4 then 'medium'
            else 'monitor'
        end as review_priority,
        case
            when budget_gap_component >= greatest(trend_component, collection_component, peer_component)
                and budget_gap_component > 0 then 'Investigate unfavorable NOI budget variance'
            when trend_component >= greatest(collection_component, peer_component)
                and trend_component > 0 then 'Investigate year-over-year NOI decline'
            when collection_component >= peer_component and collection_component > 0
                then 'Review property-level collection performance'
            when peer_component > 0 then 'Review valid-cohort NOI per unit outlier'
            else 'Monitor; no material adverse signal in the current rules'
        end as recommended_action
    from scored

)
select * from final
