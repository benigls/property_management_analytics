
with base_operation__hud_fmr as (
    select * from {{ ref('base_operation__hud_fmr') }}
),

final as (
    select
        concat_ws('|', market_id, cast(fiscal_year as varchar), cast(bedrooms as varchar)) as hud_fmr_key,
        market_id,
        county_name,
        state_code,
        bedrooms,
        fiscal_year,
        fmr_amount,
        benchmark_label,
        benchmark_source_url,
        source_system,
        source_record_id,
        source_loaded_at,
    from base_operation__hud_fmr
)
select * from final
