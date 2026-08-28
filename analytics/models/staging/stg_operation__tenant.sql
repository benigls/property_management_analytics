with source as (
    select * from {{ source('raw', 'tenants') }}
),

renamed as (
    select
        cast(tenant_id as varchar) as tenant_id,
        trim(cast(tenant_name as varchar)) as tenant_name,
        cast(created_date as date) as created_date,
        cast(source_system as varchar) as source_system,
        cast(source_record_id as varchar) as source_record_id,
        cast(source_loaded_at as timestamp) as source_loaded_at,
    from source
)
select * from renamed
