with source as (
    select * from {{ source('raw', 'vendors') }}
),

renamed as (
    select
        cast(vendor_id as varchar) as vendor_id,
        trim(cast(vendor_name as varchar)) as vendor_name,
        cast(active_from as date) as active_from,
        cast(active_to as date) as active_to,
        cast(source_system as varchar) as source_system,
        cast(source_record_id as varchar) as source_record_id,
        cast(source_loaded_at as timestamp) as source_loaded_at,
    from source
)
select * from renamed
