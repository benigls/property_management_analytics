

with rpt_financial_property__monthly as (
    select * from {{ ref('rpt_financial_property__monthly') }}
),

normalized as (
    select
        *,
        cast(noi / nullif(stated_unit_count, 0) as decimal(18, 6)) as noi_per_unit,
        cast(operating_revenue / nullif(stated_unit_count, 0) as decimal(18, 6))
            as revenue_per_unit,
        count(*) over (
            partition by performance_month, market_id, property_class
        ) as cohort_size
    from rpt_financial_property__monthly
),
eligible as (
    select
        *,
        cast(
            (sum(noi_per_unit) over cohort - noi_per_unit) / nullif(cohort_size - 1, 0)
            as decimal(18, 6)
        ) as peer_average_noi_per_unit,
        cast(
            (sum(revenue_per_unit) over cohort - revenue_per_unit) / nullif(cohort_size - 1, 0)
            as decimal(18, 6)
        ) as peer_average_revenue_per_unit
    from normalized
    where cohort_size >= 3
    window cohort as (partition by performance_month, market_id, property_class)
)
, final as (
    select
        property_id,
        property_name,
        performance_month,
        market_id,
        property_class,
        stated_unit_count,
        cohort_size,
        cohort_size - 1 as peer_property_count,
        noi_per_unit,
        peer_average_noi_per_unit,
        cast(noi_per_unit - peer_average_noi_per_unit as decimal(18, 6))
            as noi_per_unit_vs_peer,
        revenue_per_unit,
        peer_average_revenue_per_unit,
        cast(revenue_per_unit - peer_average_revenue_per_unit as decimal(18, 6))
            as revenue_per_unit_vs_peer,
        row_number() over (
            partition by performance_month, market_id, property_class
            order by noi_per_unit desc, property_id
        ) as cohort_noi_rank,
        source_loaded_at,
    from eligible

)
select * from final
