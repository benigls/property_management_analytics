

with dim_date__calendar as (
    select * from {{ ref('dim_date__calendar') }}
),
dim_property__current as (
    select * from {{ ref('dim_property__current') }}
),
dim_unit__current as (
    select * from {{ ref('dim_unit__current') }}
),
int_work_order__performance as (
    select * from {{ ref('int_work_order__performance') }}
),

months as (
    select distinct month_start_date, month_end_date
    from dim_date__calendar
    where month_start_date between {{ analytics_history_start_date() }} and {{ analytics_as_of_month_start() }}
),
property_months as (
    select
        p.property_id,
        p.property_name,
        p.market_id,
        p.property_class,
        m.month_start_date,
        m.month_end_date,
        count(u.unit_id) filter (
            where u.is_rentable
              and u.active_from <= m.month_end_date
              and (u.active_to is null or u.active_to >= m.month_end_date)
        ) as active_rentable_units
    from dim_property__current p
    cross join months m
    left join dim_unit__current u on p.property_id = u.property_id
    where p.active_from <= m.month_end_date
      and (p.active_to is null or p.active_to >= m.month_end_date)
    group by 1, 2, 3, 4, 5, 6
),
opened as (
    select
        property_id,
        date_trunc('month', opened_at)::date as month_start_date,
        count(*) as work_order_count,
        count(*) filter (where priority in ('high', 'emergency')) as high_priority_count,
        count(*) filter (where maintenance_type = 'reactive') as reactive_count,
        count(*) filter (where maintenance_type = 'preventive') as preventive_count,
        count(*) filter (where reopen_count > 0) as reopened_count,
        avg(response_hours) as average_response_hours,
        avg(resolution_hours) as average_resolution_hours,
        count(*) filter (where response_sla_met) as response_sla_met_count,
        count(*) filter (where response_sla_met is not null) as response_sla_eligible_count,
        count(*) filter (where resolution_sla_met) as resolution_sla_met_count,
        count(*) filter (where resolution_sla_met is not null) as resolution_sla_eligible_count,
        sum(labor_cost) as labor_cost,
        sum(material_cost) as material_cost,
        sum(vendor_cost) as vendor_cost,
        sum(total_cost) as total_maintenance_cost
    from int_work_order__performance
    group by 1, 2
)
, final as (
    select
        pm.*,
        coalesce(o.work_order_count, 0) as work_order_count,
        coalesce(o.high_priority_count, 0) as high_priority_count,
        coalesce(o.reactive_count, 0) as reactive_count,
        coalesce(o.preventive_count, 0) as preventive_count,
        coalesce(o.reopened_count, 0) as reopened_count,
        o.average_response_hours,
        o.average_resolution_hours,
        coalesce(o.response_sla_met_count, 0) as response_sla_met_count,
        coalesce(o.response_sla_eligible_count, 0) as response_sla_eligible_count,
        coalesce(o.resolution_sla_met_count, 0) as resolution_sla_met_count,
        coalesce(o.resolution_sla_eligible_count, 0) as resolution_sla_eligible_count,
        coalesce(o.labor_cost, 0::decimal(18, 2)) as labor_cost,
        coalesce(o.material_cost, 0::decimal(18, 2)) as material_cost,
        coalesce(o.vendor_cost, 0::decimal(18, 2)) as vendor_cost,
        coalesce(o.total_maintenance_cost, 0::decimal(18, 2)) as total_maintenance_cost,
        100.0 * coalesce(o.work_order_count, 0) / nullif(pm.active_rentable_units, 0)
            as work_orders_per_100_units,
        100.0 * coalesce(o.reactive_count, 0) / nullif(o.work_order_count, 0)
            as reactive_work_order_pct,
        100.0 * coalesce(o.response_sla_met_count, 0) / nullif(o.response_sla_eligible_count, 0)
            as response_sla_compliance_pct,
        100.0 * coalesce(o.resolution_sla_met_count, 0) / nullif(o.resolution_sla_eligible_count, 0)
            as resolution_sla_compliance_pct,
        coalesce(o.total_maintenance_cost, 0) / nullif(o.work_order_count, 0) as cost_per_work_order,
        coalesce(o.total_maintenance_cost, 0) / nullif(pm.active_rentable_units, 0) as cost_per_active_unit
    from property_months pm
    left join opened o using (property_id, month_start_date)

)
select * from final
