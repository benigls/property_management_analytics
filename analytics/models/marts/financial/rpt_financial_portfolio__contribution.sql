

with rpt_financial_property__monthly as (
    select * from {{ ref('rpt_financial_property__monthly') }}
),

portfolio as (
    select
        *,
        sum(noi) over (partition by performance_month) as portfolio_noi,
        sum(noi_favorable_variance) over (partition by performance_month)
            as portfolio_noi_favorable_variance,
        sum(case when noi_favorable_variance < 0 then abs(noi_favorable_variance) else 0 end)
            over (partition by performance_month) as portfolio_unfavorable_variance,
        sum(noi_year_over_year_change) over (partition by performance_month)
            as portfolio_noi_year_over_year_change,
        count(*) over (partition by performance_month) as portfolio_property_count,
        count(*) filter (where noi_year_over_year_change < 0)
            over (partition by performance_month) as properties_with_noi_decline
    from rpt_financial_property__monthly
)
, final as (
    select
        property_id,
        property_name,
        market_id,
        property_class,
        performance_month,
        noi,
        noi_favorable_variance,
        noi_year_over_year_change,
        portfolio_noi,
        portfolio_noi_favorable_variance,
        portfolio_noi_year_over_year_change,
        portfolio_property_count,
        properties_with_noi_decline,
        cast(noi / nullif(portfolio_noi, 0) as decimal(18, 6)) as noi_portfolio_contribution,
        cast(
            case when noi_favorable_variance < 0 then abs(noi_favorable_variance) else 0 end
            / nullif(portfolio_unfavorable_variance, 0)
            as decimal(18, 6)
        ) as unfavorable_variance_contribution,
        case
            when properties_with_noi_decline >= ceil(portfolio_property_count * 0.5)
                then 'portfolio_wide'
            else 'isolated_or_limited'
        end as adverse_trend_scope,
        source_loaded_at,
    from portfolio

)
select * from final
