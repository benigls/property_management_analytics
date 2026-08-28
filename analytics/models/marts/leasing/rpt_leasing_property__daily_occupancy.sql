

with dim_property__current as (
    select * from {{ ref('dim_property__current') }}
),
dim_date__calendar as (
    select * from {{ ref('dim_date__calendar') }}
),
dim_unit__current as (
    select * from {{ ref('dim_unit__current') }}
),
int_lease__conformed as (
    select * from {{ ref('int_lease__conformed') }}
),

property_dates as (
    select
        p.property_id,
        p.property_name,
        p.market_id,
        p.property_class,
        d.date_key as occupancy_date
    from dim_property__current p
    cross join dim_date__calendar d
    where d.date_key between {{ analytics_history_start_date() }} and {{ analytics_as_of_date() }}
      and p.active_from <= d.date_key
      and (p.active_to is null or p.active_to >= d.date_key)
),
active_units as (
    select
        pd.property_id,
        pd.property_name,
        pd.market_id,
        pd.property_class,
        pd.occupancy_date,
        u.unit_id
    from property_dates pd
    inner join dim_unit__current u on pd.property_id = u.property_id
    where u.is_rentable
      and u.active_from <= pd.occupancy_date
      and (u.active_to is null or u.active_to >= pd.occupancy_date)
),
unit_coverage as (
    select
        au.*,
        max(
            case
                when l.lease_id is not null
                  and l.lease_start_date <= au.occupancy_date
                  and l.lease_end_date >= au.occupancy_date
                  and coalesce(l.move_in_date, l.lease_start_date) <= au.occupancy_date
                  and (l.move_out_date is null or l.move_out_date >= au.occupancy_date)
                then 1 else 0
            end
        ) as is_occupied
    from active_units au
    left join int_lease__conformed l on au.unit_id = l.unit_id
    group by all
)
, final as (
    select
        property_id,
        property_name,
        market_id,
        property_class,
        occupancy_date,
        count(*)::integer as active_rentable_units,
        sum(is_occupied)::integer as occupied_units,
        (count(*) - sum(is_occupied))::integer as vacant_units,
        cast(100.0 * sum(is_occupied) / nullif(count(*), 0) as decimal(7, 2))
            as physical_occupancy_pct,
        {{ analytics_as_of_date() }} as analytics_as_of_date
    from unit_coverage
    group by 1, 2, 3, 4, 5
)
select * from final
