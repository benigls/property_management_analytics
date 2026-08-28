

with dim_date__calendar as (
    select * from {{ ref('dim_date__calendar') }}
),
int_work_order__conformed as (
    select * from {{ ref('int_work_order__conformed') }}
),
int_work_order_status__history as (
    select * from {{ ref('int_work_order_status__history') }}
),
dim_operations_sla__policy as (
    select * from {{ ref('dim_operations_sla__policy') }}
),
rpt_operations_property__monthly as (
    select * from {{ ref('rpt_operations_property__monthly') }}
),

snapshots as (
    select distinct
        month_start_date,
        month_end_date,
        cast(month_end_date as timestamp) + interval 23 hours + interval 59 minutes + interval 59 seconds
            as snapshot_at
    from dim_date__calendar
    where month_start_date between {{ analytics_history_start_date() }} and {{ analytics_as_of_month_start() }}
),
work_order_snapshot as (
    select
        s.month_start_date,
        s.month_end_date,
        s.snapshot_at,
        w.work_order_id,
        w.property_id,
        w.opened_at,
        w.priority,
        policy.resolution_target_hours,
        arg_max(h.work_order_status, h.event_sequence) as status_at_snapshot
    from snapshots s
    inner join int_work_order__conformed w on w.opened_at <= s.snapshot_at
    inner join int_work_order_status__history h
        on w.work_order_id = h.work_order_id
        and h.event_at <= s.snapshot_at
    inner join dim_operations_sla__policy policy
        on w.priority = policy.priority
        and cast(w.opened_at as date) >= policy.effective_from
        and (policy.effective_to is null or cast(w.opened_at as date) <= policy.effective_to)
    group by 1, 2, 3, 4, 5, 6, 7, 8
),
aggregated as (
    select
        property_id,
        month_start_date,
        month_end_date,
        snapshot_at,
        count(*) filter (where status_at_snapshot <> 'closed') as backlog_count,
        count(*) filter (
            where status_at_snapshot <> 'closed' and priority in ('high', 'emergency')
        ) as high_priority_backlog_count,
        count(*) filter (
            where status_at_snapshot <> 'closed'
              and date_diff('second', opened_at, snapshot_at) / 3600.0 > resolution_target_hours
        ) as breached_backlog_count,
        avg(date_diff('second', opened_at, snapshot_at) / 86400.0)
            filter (where status_at_snapshot <> 'closed') as average_backlog_age_days,
        max(date_diff('second', opened_at, snapshot_at) / 86400.0)
            filter (where status_at_snapshot <> 'closed') as oldest_backlog_age_days
    from work_order_snapshot
    group by 1, 2, 3, 4
)
, final as (
    select
        pm.property_id,
        pm.property_name,
        pm.market_id,
        pm.property_class,
        pm.month_start_date,
        pm.month_end_date,
        cast(pm.month_end_date as timestamp) + interval 23 hours + interval 59 minutes + interval 59 seconds
            as snapshot_at,
        coalesce(a.backlog_count, 0) as backlog_count,
        coalesce(a.high_priority_backlog_count, 0) as high_priority_backlog_count,
        coalesce(a.breached_backlog_count, 0) as breached_backlog_count,
        cast(a.average_backlog_age_days as decimal(18, 6)) as average_backlog_age_days,
        cast(a.oldest_backlog_age_days as decimal(18, 6)) as oldest_backlog_age_days,
        coalesce(a.backlog_count, 0) - lag(coalesce(a.backlog_count, 0)) over (
            partition by pm.property_id order by pm.month_start_date
        ) as backlog_month_over_month_change
    from rpt_operations_property__monthly pm
    left join aggregated a using (property_id, month_start_date, month_end_date)
)
select * from final
