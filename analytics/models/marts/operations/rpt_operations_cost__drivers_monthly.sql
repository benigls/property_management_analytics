

with rpt_operations_property__monthly as (
    select * from {{ ref('rpt_operations_property__monthly') }}
),
int_work_order__performance as (
    select * from {{ ref('int_work_order__performance') }}
),
dim_operations_sla__policy as (
    select * from {{ ref('dim_operations_sla__policy') }}
),

property_totals as (
    select
        pm.*,
        lag(work_order_count) over (
            partition by property_id order by month_start_date
        ) as prior_work_order_count,
        lag(total_maintenance_cost) over (
            partition by property_id order by month_start_date
        ) as prior_total_maintenance_cost,
        lag(cost_per_work_order) over (
            partition by property_id order by month_start_date
        ) as prior_cost_per_work_order
    from rpt_operations_property__monthly pm
),
priority_activity as (
    select
        property_id,
        date_trunc('month', opened_at)::date as month_start_date,
        priority,
        count(*) as priority_work_order_count,
        sum(total_cost) as priority_cost,
        sum(total_cost) / nullif(count(*), 0) as priority_cost_per_order
    from int_work_order__performance
    group by 1, 2, 3
),
priority_grid as (
    select
        p.property_id,
        p.month_start_date,
        policy.priority,
        coalesce(a.priority_work_order_count, 0) as priority_work_order_count,
        coalesce(a.priority_cost, 0::decimal(18, 2)) as priority_cost,
        a.priority_cost_per_order
    from property_totals p
    cross join dim_operations_sla__policy policy
    left join priority_activity a
        on p.property_id = a.property_id
        and p.month_start_date = a.month_start_date
        and policy.priority = a.priority
),
with_previous as (
    select
        current.*,
        lag(priority_work_order_count) over (
            partition by property_id, priority order by month_start_date
        ) as prior_priority_work_order_count,
        lag(priority_cost_per_order) over (
            partition by property_id, priority order by month_start_date
        ) as prior_priority_cost_per_order
    from priority_grid current
),
effects as (
    select
        p.property_id,
        p.month_start_date,
        p.property_name,
        p.market_id,
        p.property_class,
        p.active_rentable_units,
        p.work_order_count,
        p.high_priority_count,
        p.total_maintenance_cost,
        p.cost_per_work_order,
        p.cost_per_active_unit,
        p.prior_work_order_count,
        p.prior_total_maintenance_cost,
        p.prior_cost_per_work_order,
        (p.work_order_count - p.prior_work_order_count) * p.prior_cost_per_work_order
            as volume_cost_effect,
        sum(
            (coalesce(m.priority_work_order_count, 0)
                - p.work_order_count * coalesce(m.prior_priority_work_order_count, 0)
                    / nullif(p.prior_work_order_count, 0))
            * coalesce(m.prior_priority_cost_per_order, p.prior_cost_per_work_order)
        ) as severity_mix_cost_effect,
        sum(
            coalesce(m.priority_work_order_count, 0)
            * (m.priority_cost_per_order
                - coalesce(m.prior_priority_cost_per_order, p.prior_cost_per_work_order))
        ) as unit_cost_effect
    from property_totals p
    inner join with_previous m
        on p.property_id = m.property_id
        and p.month_start_date = m.month_start_date
    group by all
)
, final as (
    select
        property_id,
        month_start_date,
        property_name,
        market_id,
        property_class,
        active_rentable_units,
        work_order_count,
        high_priority_count,
        total_maintenance_cost,
        cast(cost_per_work_order as decimal(18, 6)) as cost_per_work_order,
        cast(cost_per_active_unit as decimal(18, 6)) as cost_per_active_unit,
        prior_work_order_count,
        prior_total_maintenance_cost,
        cast(prior_cost_per_work_order as decimal(18, 6)) as prior_cost_per_work_order,
        cast(volume_cost_effect as decimal(18, 6)) as volume_cost_effect,
        cast(severity_mix_cost_effect as decimal(18, 6)) as severity_mix_cost_effect,
        cast(unit_cost_effect as decimal(18, 6)) as unit_cost_effect,
        cast(total_maintenance_cost - prior_total_maintenance_cost as decimal(18, 2))
            as total_cost_change,
        cast(total_maintenance_cost - prior_total_maintenance_cost
            - coalesce(volume_cost_effect, 0)
            - coalesce(severity_mix_cost_effect, 0)
            - coalesce(unit_cost_effect, 0) as decimal(18, 6)) as decomposition_residual,
        case
            when prior_total_maintenance_cost is null then 'no_prior_period'
            when abs(coalesce(volume_cost_effect, 0)) >= greatest(
                abs(coalesce(severity_mix_cost_effect, 0)), abs(coalesce(unit_cost_effect, 0))
            ) then 'volume'
            when abs(coalesce(severity_mix_cost_effect, 0)) >= abs(coalesce(unit_cost_effect, 0))
                then 'severity_mix'
            else 'cost_per_order'
        end as primary_cost_driver
    from effects
)
select * from final
