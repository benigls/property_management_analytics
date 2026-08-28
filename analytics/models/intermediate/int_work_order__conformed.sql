with base_work_order as (
    select * from {{ ref('base_operation__work_order') }}
),

final as (
    select
        w.work_order_id,
        w.property_id,
        w.unit_id,
        w.vendor_id,
        w.opened_at,
        w.first_response_at,
        w.closed_at,
        w.work_order_status,
        w.priority,
        w.category,
        w.maintenance_type,
        w.labor_cost,
        w.material_cost,
        w.vendor_cost,
        cast(w.labor_cost + w.material_cost + w.vendor_cost as decimal(18, 2)) as total_cost,
        w.source_system,
        w.source_record_id,
        w.source_loaded_at,
    from base_work_order as w
)
select * from final
