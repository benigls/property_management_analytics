with latest_backlog as (
    select property_id, backlog_count
    from {{ ref('rpt_operations_backlog__monthly') }}
    where month_start_date = date '2026-06-01'
),
queue as (
    select property_id, count(*) as queue_count
    from {{ ref('rpt_operations_action__queue') }}
    group by 1
)
select
    b.property_id,
    b.backlog_count,
    coalesce(q.queue_count, 0) as queue_count
from latest_backlog b
left join queue q using (property_id)
where b.backlog_count <> coalesce(q.queue_count, 0)

