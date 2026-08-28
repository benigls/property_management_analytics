

with int_work_order__performance as (
    select * from {{ ref('int_work_order__performance') }}
),
rpt_operations_property__monthly as (
    select * from {{ ref('rpt_operations_property__monthly') }}
),

categories as (
    select distinct category from int_work_order__performance
),
category_activity as (
    select
        property_id,
        date_trunc('month', opened_at)::date as month_start_date,
        category,
        count(*) as work_order_count,
        sum(total_cost) as total_cost,
        avg(resolution_hours) as average_resolution_hours
    from int_work_order__performance
    group by 1, 2, 3
),
grid as (
    select
        pm.property_id,
        pm.property_name,
        pm.market_id,
        pm.property_class,
        pm.month_start_date,
        pm.month_end_date,
        pm.active_rentable_units,
        c.category
    from rpt_operations_property__monthly pm
    cross join categories c
),
prepared as (
    select
        g.*,
        coalesce(a.work_order_count, 0) as work_order_count,
        coalesce(a.total_cost, 0::decimal(18, 2)) as total_cost,
        a.average_resolution_hours
    from grid g
    left join category_activity a using (property_id, month_start_date, category)
)
, final as (
    select
        *,
        100.0 * work_order_count / nullif(active_rentable_units, 0) as work_orders_per_100_units,
        work_order_count - lag(work_order_count) over (
            partition by property_id, category order by month_start_date
        ) as work_order_month_over_month_change,
        total_cost - lag(total_cost) over (
            partition by property_id, category order by month_start_date
        ) as cost_month_over_month_change
    from prepared

)
select * from final
