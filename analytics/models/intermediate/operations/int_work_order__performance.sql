{{ config(materialized='view', schema='operations') }}

with work_orders as (
    select * from {{ ref('int_work_order__conformed') }}
),

status_history as (
    select * from {{ ref('int_work_order_status__history') }}
),

properties as (
    select * from {{ ref('base_operation__property') }}
),

units as (
    select * from {{ ref('base_operation__unit') }}
),

vendors as (
    select * from {{ ref('base_operation__vendor') }}
),

event_summary as (
    select
        work_order_id,
        arg_max(work_order_status, event_sequence) as latest_status,
        arg_max(event_at, event_sequence) as latest_status_at,
        max(event_at) filter (where work_order_status = 'closed') as latest_closed_event_at,
        count(*) filter (where work_order_status = 'reopened') as reopen_count
    from status_history
    where event_at <= {{ analytics_cutoff_timestamp() }}
    group by 1
),
prepared as (
    select
        w.*,
        coalesce(e.latest_status, w.work_order_status) as latest_status,
        e.latest_status_at,
        case when e.latest_status = 'closed' then e.latest_closed_event_at end as valid_closed_at,
        coalesce(e.reopen_count, 0) as reopen_count,
        p.property_name,
        p.market_id,
        p.property_class,
        u.unit_number,
        v.vendor_name,
        policy.policy_version,
        policy.response_target_hours,
        policy.resolution_target_hours
    from work_orders as w
    left join event_summary e using (work_order_id)
    inner join properties as p using (property_id)
    inner join units as u using (unit_id, property_id)
    left join vendors as v using (vendor_id)
    inner join (
        select * from (values
            (
                'OPS-SLA-2023-01', 'emergency', 1.0, 8.0,
                {{ analytics_history_start_date() }}, null::date
            ),
            (
                'OPS-SLA-2023-01', 'high', 4.0, 24.0,
                {{ analytics_history_start_date() }}, null::date
            ),
            (
                'OPS-SLA-2023-01', 'normal', 24.0, 72.0,
                {{ analytics_history_start_date() }}, null::date
            ),
            (
                'OPS-SLA-2023-01', 'low', 48.0, 120.0,
                {{ analytics_history_start_date() }}, null::date
            )
        ) as policy_values(
            policy_version,
            priority,
            response_target_hours,
            resolution_target_hours,
            effective_from,
            effective_to
        )
    ) as policy
        on w.priority = policy.priority
        and cast(w.opened_at as date) >= policy.effective_from
        and (policy.effective_to is null or cast(w.opened_at as date) <= policy.effective_to)
)
, final as (
    select
        work_order_id,
        property_id,
        property_name,
        market_id,
        property_class,
        unit_id,
        unit_number,
        vendor_id,
        vendor_name,
        opened_at,
        first_response_at,
        valid_closed_at,
        latest_status,
        latest_status_at,
        priority,
        category,
        maintenance_type,
        labor_cost,
        material_cost,
        vendor_cost,
        total_cost,
        reopen_count,
        policy_version,
        response_target_hours,
        resolution_target_hours,
        date_diff('second', opened_at, first_response_at) / 3600.0 as response_hours,
        date_diff('second', opened_at, valid_closed_at) / 3600.0 as resolution_hours,
        case
            when first_response_at is not null
                then date_diff('second', opened_at, first_response_at) / 3600.0 <= response_target_hours
            when date_diff('second', opened_at, {{ analytics_cutoff_timestamp() }}) / 3600.0
                > response_target_hours then false
        end as response_sla_met,
        case
            when valid_closed_at is not null
                then date_diff('second', opened_at, valid_closed_at) / 3600.0 <= resolution_target_hours
            when date_diff('second', opened_at, {{ analytics_cutoff_timestamp() }}) / 3600.0
                > resolution_target_hours then false
        end as resolution_sla_met,
        latest_status <> 'closed' as is_open_as_of_cutoff,
        case
            when latest_status <> 'closed'
                then date_diff('second', opened_at, {{ analytics_cutoff_timestamp() }}) / 3600.0
        end as open_age_hours,
        source_system,
        source_record_id,
        source_loaded_at,
        {{ analytics_as_of_date() }} as analytics_cutoff_date
    from prepared
)
select * from final
