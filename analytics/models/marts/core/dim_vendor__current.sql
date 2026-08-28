
with base_operation__vendor as (
    select * from {{ ref('base_operation__vendor') }}
),

final as (
    select
        vendor_id,
        vendor_name,
        active_from,
        active_to,
        source_system,
        source_record_id,
        source_loaded_at,
    from base_operation__vendor
)
select * from final
