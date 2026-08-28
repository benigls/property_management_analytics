with source as (
    select * from {{ source('raw', 'units') }}
),

renamed as (
    select
        cast(unit_id as varchar) as unit_id,
        cast(property_id as varchar) as property_id,
        trim(cast(unit_number as varchar)) as unit_number,
        cast(market_rent as decimal(18, 2)) as market_rent,
        cast(is_rentable as boolean) as is_rentable,
        cast(active_from as date) as active_from,
        cast(active_to as date) as active_to,
        cast(source_system as varchar) as source_system,
        cast(source_record_id as varchar) as source_record_id,
        cast(source_loaded_at as timestamp) as source_loaded_at,
    from source
)
select * from renamed
