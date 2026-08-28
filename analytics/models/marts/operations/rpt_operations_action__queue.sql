

with int_work_order__performance as (
    select * from {{ ref('int_work_order__performance') }}
),

final as (
    select
        work_order_id,
        property_id,
        property_name,
        unit_id,
        unit_number,
        priority,
        category,
        maintenance_type,
        opened_at,
        latest_status,
        latest_status_at,
        open_age_hours,
        open_age_hours / 24.0 as open_age_days,
        response_target_hours,
        resolution_target_hours,
        response_sla_met,
        resolution_sla_met,
        total_cost,
        case priority
            when 'emergency' then 4
            when 'high' then 3
            when 'normal' then 2
            else 1
        end as priority_weight,
        case
            when resolution_sla_met = false then 'Escalate breached resolution SLA'
            when response_sla_met = false then 'Review delayed first response'
            else 'Monitor open work'
        end as recommended_action,
        policy_version,
        analytics_cutoff_date
    from int_work_order__performance
    where is_open_as_of_cutoff

)
select * from final
