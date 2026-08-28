with base_work_order_status as (
    select * from {{ ref('base_operation__work_order_status') }}
),

work_orders as (
    select * from {{ ref('int_work_order__conformed') }}
),

final as (
    select
        h.status_event_id,
        h.work_order_id,
        w.property_id,
        w.unit_id,
        h.work_order_status,
        h.event_at,
        h.event_sequence,
        h.source_system,
        h.source_record_id,
        h.source_loaded_at,
    from base_work_order_status as h
    inner join work_orders as w on h.work_order_id = w.work_order_id
)
select * from final
