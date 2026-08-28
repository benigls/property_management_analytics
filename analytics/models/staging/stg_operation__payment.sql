with source as (
    select * from {{ source('raw', 'payments') }}
),

renamed as (
    select
        cast(payment_id as varchar) as payment_id,
        cast(property_id as varchar) as property_id,
        cast(tenant_id as varchar) as tenant_id,
        cast(payment_date as date) as payment_date,
        cast(amount as decimal(18, 2)) as payment_amount,
        lower(trim(cast(status as varchar))) as payment_status,
        cast(posted_at as timestamp) as posted_at,
        cast(source_system as varchar) as source_system,
        cast(source_record_id as varchar) as source_record_id,
        cast(source_loaded_at as timestamp) as source_loaded_at,
    from source
)
select * from renamed
