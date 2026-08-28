

with rpt_leasing_property__daily_occupancy as (
    select * from {{ ref('rpt_leasing_property__daily_occupancy') }}
),

final as (
    select
        property_id,
        property_name,
        market_id,
        property_class,
        occupancy_date as month_end_date,
        active_rentable_units,
        occupied_units,
        vacant_units,
        physical_occupancy_pct,
        analytics_as_of_date
    from rpt_leasing_property__daily_occupancy
    where occupancy_date = last_day(occupancy_date)
)
select * from final
