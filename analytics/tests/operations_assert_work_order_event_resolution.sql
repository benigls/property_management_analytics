with expected as (
    select
        work_order_id,
        arg_max(work_order_status, event_sequence) as expected_latest_status,
        max(event_at) filter (where work_order_status = 'closed') as latest_close_event
    from {{ ref('int_work_order_status__history') }}
    where event_at <= timestamp '2026-06-30 23:59:59'
    group by 1
)
select w.work_order_id
from {{ ref('int_work_order__performance') }} w
inner join expected e using (work_order_id)
where w.latest_status <> e.expected_latest_status
   or (e.expected_latest_status = 'closed' and w.valid_closed_at <> e.latest_close_event)
   or (e.expected_latest_status <> 'closed' and w.valid_closed_at is not null)

