with source as (
    select * from {{ source('raw', 'charges') }}
),

renamed as (
    select
        cast(charge_id as varchar) as charge_id,
        cast(property_id as varchar) as property_id,
        cast(unit_id as varchar) as unit_id,
        cast(lease_id as varchar) as lease_id,
        cast(tenant_id as varchar) as tenant_id,
        cast(charge_date as date) as charge_date,
        cast(due_date as date) as due_date,
        lower(trim(cast(charge_type as varchar))) as charge_type,
        cast(amount as decimal(18, 2)) as charge_amount,
        cast(approved_credit_amount as decimal(18, 2)) as approved_credit_amount,
        cast(posted_at as timestamp) as posted_at,
        cast(source_system as varchar) as source_system,
        cast(source_record_id as varchar) as source_record_id,
        cast(source_loaded_at as timestamp) as source_loaded_at,
    from source
)
select * from renamed
