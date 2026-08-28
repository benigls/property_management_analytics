

with dim_date__calendar as (
    select * from {{ ref('dim_date__calendar') }}
),
dim_property__current as (
    select * from {{ ref('dim_property__current') }}
),
dim_unit__current as (
    select * from {{ ref('dim_unit__current') }}
),
int_lease__conformed as (
    select * from {{ ref('int_lease__conformed') }}
),
rpt_leasing_renewal__turnover as (
    select * from {{ ref('rpt_leasing_renewal__turnover') }}
),
rpt_leasing_vacancy__episode as (
    select * from {{ ref('rpt_leasing_vacancy__episode') }}
),
rpt_leasing_expiration__exposure as (
    select * from {{ ref('rpt_leasing_expiration__exposure') }}
),

forecast_months as (
    select month_end_date as forecast_month_end
    from dim_date__calendar
    where date_key = month_end_date
      and date_key > {{ analytics_as_of_date() }}
      and date_key <= {{ analytics_forecast_end_date() }}
),
property_months as (
    select
        p.property_id,
        p.property_name,
        p.market_id,
        p.property_class,
        fm.forecast_month_end
    from dim_property__current p
    cross join forecast_months fm
    where p.active_from <= fm.forecast_month_end
      and (p.active_to is null or p.active_to >= fm.forecast_month_end)
),
active_unit_counts as (
    select
        pm.property_id,
        pm.forecast_month_end,
        count(*)::integer as active_rentable_units
    from property_months pm
    inner join dim_unit__current u on pm.property_id = u.property_id
    where u.is_rentable
      and u.active_from <= pm.forecast_month_end
      and (u.active_to is null or u.active_to >= pm.forecast_month_end)
    group by 1, 2
),
committed as (
    select
        pm.property_id,
        pm.forecast_month_end,
        count(distinct l.unit_id)::integer as committed_occupied_units
    from property_months pm
    left join int_lease__conformed l
      on pm.property_id = l.property_id
     and l.signed_date <= {{ analytics_as_of_date() }}
     and l.lease_start_date <= pm.forecast_month_end
     and l.lease_end_date >= pm.forecast_month_end
    group by 1, 2
),
property_renewal as (
    select
        property_id,
        avg(case when is_renewal then 1.0 else 0.0 end) as historical_renewal_rate
    from rpt_leasing_renewal__turnover
    group by 1
),
peer_renewal as (
    select
        market_id,
        property_class,
        avg(case when is_renewal then 1.0 else 0.0 end) as peer_renewal_rate
    from rpt_leasing_renewal__turnover
    group by 1, 2
),
property_vacancy as (
    select property_id, avg(vacancy_days) as historical_avg_vacancy_days
    from rpt_leasing_vacancy__episode
    group by 1
),
peer_vacancy as (
    select market_id, property_class, avg(vacancy_days) as peer_avg_vacancy_days
    from rpt_leasing_vacancy__episode
    group by 1, 2
),
unresolved_expirations as (
    select
        e.property_id,
        pm.forecast_month_end,
        e.lease_id,
        e.expiration_date,
        coalesce(pr.historical_renewal_rate, per.peer_renewal_rate, 0.75) as renewal_rate,
        coalesce(pv.historical_avg_vacancy_days, pev.peer_avg_vacancy_days, 30.0)
            as average_vacancy_days
    from rpt_leasing_expiration__exposure e
    inner join property_months pm on e.property_id = pm.property_id
    left join property_renewal pr on e.property_id = pr.property_id
    left join peer_renewal per
      on pm.market_id = per.market_id and pm.property_class = per.property_class
    left join property_vacancy pv on e.property_id = pv.property_id
    left join peer_vacancy pev
      on pm.market_id = pev.market_id and pm.property_class = pev.property_class
    where not e.is_mitigated
      and e.expiration_date < pm.forecast_month_end
),
base_adjustments as (
    select
        property_id,
        forecast_month_end,
        count(*)::integer as unresolved_expired_units,
        sum(
            renewal_rate
            + (1.0 - renewal_rate) * least(
                1.0,
                greatest(
                    0.0,
                    date_diff('day', expiration_date, forecast_month_end)
                    / nullif(average_vacancy_days, 0)
                )
            )
        ) as expected_occupied_from_unresolved
    from unresolved_expirations
    group by 1, 2
)
, final as (
    select
        pm.property_id,
        pm.property_name,
        pm.market_id,
        pm.property_class,
        pm.forecast_month_end,
        auc.active_rentable_units,
        c.committed_occupied_units,
        cast(100.0 * c.committed_occupied_units / nullif(auc.active_rentable_units, 0)
            as decimal(7, 2)) as committed_occupancy_pct,
        coalesce(ba.unresolved_expired_units, 0) as unresolved_expired_units,
        cast(coalesce(ba.expected_occupied_from_unresolved, 0) as decimal(18, 2))
            as expected_occupied_from_unresolved,
        least(
            auc.active_rentable_units,
            cast(c.committed_occupied_units + coalesce(ba.expected_occupied_from_unresolved, 0)
                as decimal(18, 2))
        ) as base_scenario_occupied_units,
        cast(
            100.0 * least(
                auc.active_rentable_units,
                c.committed_occupied_units + coalesce(ba.expected_occupied_from_unresolved, 0)
            ) / nullif(auc.active_rentable_units, 0)
            as decimal(7, 2)
        ) as base_scenario_occupancy_pct,
        'Estimate using signed coverage plus historical renewal and vacancy behavior for unresolved expirations.'
            as base_scenario_method,
        {{ analytics_as_of_date() }} as analytics_as_of_date
    from property_months pm
    inner join active_unit_counts auc using (property_id, forecast_month_end)
    inner join committed c using (property_id, forecast_month_end)
    left join base_adjustments ba using (property_id, forecast_month_end)
)
select * from final
