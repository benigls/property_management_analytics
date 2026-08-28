with source as (
    select * from {{ source('raw', 'work_orders') }}
),

renamed as (
    select
        cast(work_order_id as varchar) as work_order_id,
        cast(property_id as varchar) as property_id,
        cast(unit_id as varchar) as unit_id,
        cast(vendor_id as varchar) as vendor_id,
        cast(opened_at as timestamp) as opened_at,
        cast(first_response_at as timestamp) as first_response_at,
        cast(closed_at as timestamp) as closed_at,
        lower(trim(cast(status as varchar))) as work_order_status,
        lower(trim(cast(priority as varchar))) as priority,
        lower(trim(cast(category as varchar))) as category,
        lower(trim(cast(maintenance_type as varchar))) as maintenance_type,
        cast(labor_cost as decimal(18, 2)) as labor_cost,
        cast(material_cost as decimal(18, 2)) as material_cost,
        cast(vendor_cost as decimal(18, 2)) as vendor_cost,
        cast(source_system as varchar) as source_system,
        cast(source_record_id as varchar) as source_record_id,
        cast(source_loaded_at as timestamp) as source_loaded_at,
    from source
)
select * from renamed
