with source as (
    select * from {{ source('raw', 'payment_allocations') }}
),

renamed as (
    select
        cast(payment_allocation_id as varchar) as payment_allocation_id,
        cast(payment_id as varchar) as payment_id,
        cast(charge_id as varchar) as charge_id,
        cast(allocated_amount as decimal(18, 2)) as allocated_amount,
        cast(allocation_date as date) as allocation_date,
        cast(source_system as varchar) as source_system,
        cast(source_record_id as varchar) as source_record_id,
        cast(source_loaded_at as timestamp) as source_loaded_at,
    from source
)
select * from renamed
