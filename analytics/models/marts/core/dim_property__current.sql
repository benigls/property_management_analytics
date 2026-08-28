
with base_operation__property as (
    select * from {{ ref('base_operation__property') }}
),

final as (
    select
        property_id,
        property_name,
        market_id,
        property_class,
        stated_unit_count,
        active_from,
        active_to,
        source_system,
        source_record_id,
        source_loaded_at,
    from base_operation__property
)
select * from final
