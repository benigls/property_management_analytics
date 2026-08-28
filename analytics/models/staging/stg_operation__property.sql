with source as (
    select * from {{ source('raw', 'properties') }}
),

renamed as (
    select
        cast(property_id as varchar) as property_id,
        trim(cast(property_name as varchar)) as property_name,
        upper(trim(cast(market_id as varchar))) as market_id,
        upper(trim(cast(property_class as varchar))) as property_class,
        cast(unit_count as integer) as stated_unit_count,
        cast(active_from as date) as active_from,
        cast(active_to as date) as active_to,
        cast(source_system as varchar) as source_system,
        cast(source_record_id as varchar) as source_record_id,
        cast(source_loaded_at as timestamp) as source_loaded_at,
    from source
)
select * from renamed
