

with policy(
    policy_version,
    priority,
    response_target_hours,
    resolution_target_hours,
    effective_from,
    effective_to
) as (
    values
        ('OPS-SLA-2023-01', 'emergency', 1.0, 8.0, {{ analytics_history_start_date() }}, null::date),
        ('OPS-SLA-2023-01', 'high', 4.0, 24.0, {{ analytics_history_start_date() }}, null::date),
        ('OPS-SLA-2023-01', 'normal', 24.0, 72.0, {{ analytics_history_start_date() }}, null::date),
        ('OPS-SLA-2023-01', 'low', 48.0, 120.0, {{ analytics_history_start_date() }}, null::date)
)
, final as (
    select
        policy_version,
        priority,
        response_target_hours,
        resolution_target_hours,
        effective_from,
        effective_to
    from policy
)
select * from final
