with source as (
    select * from {{ source('raw', 'leases') }}
),

renamed as (
    select
        cast(lease_id as varchar) as lease_id,
        cast(property_id as varchar) as property_id,
        cast(unit_id as varchar) as unit_id,
        cast(tenant_id as varchar) as tenant_id,
        cast(lease_start_date as date) as lease_start_date,
        cast(lease_end_date as date) as lease_end_date,
        cast(move_in_date as date) as move_in_date,
        cast(move_out_date as date) as move_out_date,
        cast(signed_date as date) as signed_date,
        cast(monthly_rent as decimal(18, 2)) as monthly_rent,
        cast(renewal_of_lease_id as varchar) as renewal_of_lease_id,
        lower(trim(cast(outcome as varchar))) as lease_outcome,
        cast(source_system as varchar) as source_system,
        cast(source_record_id as varchar) as source_record_id,
        cast(source_loaded_at as timestamp) as source_loaded_at,
    from source
)
select * from renamed
