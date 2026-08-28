with source as (
    select * from {{ source('raw', 'hud_fmr') }}
),

renamed as (
    select
        upper(trim(cast(market_id as varchar))) as market_id,
        trim(cast(county_name as varchar)) as county_name,
        upper(trim(cast(state_code as varchar))) as state_code,
        cast(bedrooms as integer) as bedrooms,
        cast(fiscal_year as integer) as fiscal_year,
        cast(fmr_amount as decimal(18, 2)) as fmr_amount,
        cast(benchmark_label as varchar) as benchmark_label,
        cast(source_url as varchar) as benchmark_source_url,
        cast(source_system as varchar) as source_system,
        cast(source_record_id as varchar) as source_record_id,
        cast(source_loaded_at as timestamp) as source_loaded_at,
    from source
)
select * from renamed
