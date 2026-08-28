
with base_operation__tenant as (
    select * from {{ ref('base_operation__tenant') }}
),

final as (
    select
        tenant_id,
        tenant_name,
        created_date,
        source_system,
        source_record_id,
        source_loaded_at,
    from base_operation__tenant
)
select * from final
