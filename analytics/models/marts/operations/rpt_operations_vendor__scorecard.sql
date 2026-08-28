

with int_work_order__performance as (
    select * from {{ ref('int_work_order__performance') }}
),
dim_vendor__current as (
    select * from {{ ref('dim_vendor__current') }}
),

vendor_performance as (
    select
        w.vendor_id,
        v.vendor_name,
        w.category,
        w.priority,
        count(*) as comparable_completed_count,
        avg(w.resolution_hours) as average_resolution_hours,
        avg(w.total_cost) as average_cost_per_order,
        100.0 * count(*) filter (where w.resolution_sla_met) / nullif(count(*), 0)
            as resolution_sla_compliance_pct,
        sum(w.total_cost) as total_cost
    from int_work_order__performance w
    inner join dim_vendor__current v using (vendor_id)
    where w.valid_closed_at is not null
      and w.vendor_id is not null
    group by 1, 2, 3, 4
),
eligible as (
    select
        vendor_id,
        vendor_name,
        category,
        priority,
        comparable_completed_count,
        average_resolution_hours,
        average_cost_per_order,
        resolution_sla_compliance_pct,
        total_cost
    from vendor_performance
    where comparable_completed_count >= 20
),
benchmarks as (
    select
        category,
        priority,
        count(*) as eligible_vendor_count,
        sum(average_cost_per_order * comparable_completed_count)
            / sum(comparable_completed_count) as peer_average_cost_per_order,
        sum(average_resolution_hours * comparable_completed_count)
            / sum(comparable_completed_count) as peer_average_resolution_hours,
        sum(resolution_sla_compliance_pct * comparable_completed_count)
            / sum(comparable_completed_count) as peer_resolution_sla_compliance_pct
    from eligible
    group by 1, 2
)
, final as (
    select
        v.vendor_id,
        v.vendor_name,
        v.category,
        v.priority,
        v.comparable_completed_count,
        cast(v.average_resolution_hours as decimal(18, 6)) as average_resolution_hours,
        cast(v.average_cost_per_order as decimal(18, 6)) as average_cost_per_order,
        cast(v.resolution_sla_compliance_pct as decimal(18, 6))
            as resolution_sla_compliance_pct,
        v.total_cost,
        coalesce(b.eligible_vendor_count, 0) as eligible_vendor_count,
        cast(case when v.comparable_completed_count >= 20 and b.eligible_vendor_count >= 2
            then b.peer_average_cost_per_order end as decimal(18, 6))
            as peer_average_cost_per_order,
        cast(case when v.comparable_completed_count >= 20 and b.eligible_vendor_count >= 2
            then b.peer_average_resolution_hours end as decimal(18, 6))
            as peer_average_resolution_hours,
        cast(case when v.comparable_completed_count >= 20 and b.eligible_vendor_count >= 2
            then b.peer_resolution_sla_compliance_pct end as decimal(18, 6))
            as peer_resolution_sla_compliance_pct,
        cast(case when v.comparable_completed_count >= 20 and b.eligible_vendor_count >= 2
            then v.average_cost_per_order - b.peer_average_cost_per_order end as decimal(18, 6))
            as cost_per_order_delta,
        cast(case when v.comparable_completed_count >= 20 and b.eligible_vendor_count >= 2
            then v.average_resolution_hours - b.peer_average_resolution_hours end as decimal(18, 6))
            as resolution_hours_delta,
        cast(case when v.comparable_completed_count >= 20 and b.eligible_vendor_count >= 2
            then v.resolution_sla_compliance_pct - b.peer_resolution_sla_compliance_pct end
            as decimal(18, 6)) as sla_compliance_percentage_point_delta,
        case
            when v.comparable_completed_count < 20 then 'insufficient_vendor_sample'
            when coalesce(b.eligible_vendor_count, 0) < 2 then 'insufficient_peer_vendors'
            else 'comparable'
        end as comparison_status
    from vendor_performance v
    left join benchmarks b using (category, priority)
)
select * from final
