with stg_operation__work_order_status as (
    select * from {{ ref('stg_operation__work_order_status') }}
),
base_operation__work_order as (
    select * from {{ ref('base_operation__work_order') }}
),

final as (
    select h.*
    from stg_operation__work_order_status h
    -- Keep sequenced status events after the work order opened.
    inner join base_operation__work_order w on h.work_order_id = w.work_order_id
    where h.status_event_id is not null
      and h.event_at >= w.opened_at
      and h.event_sequence > 0
)
select * from final
