
with base_operation__unit as (
    select * from {{ ref('base_operation__unit') }}
),
dim_property__current as (
    select * from {{ ref('dim_property__current') }}
),

final as (
    select
        u.unit_id,
        u.property_id,
        u.unit_number,
        u.market_rent,
        u.is_rentable,
        u.active_from,
        u.active_to,
        u.source_system,
        u.source_record_id,
        u.source_loaded_at,
    from base_operation__unit u
    inner join dim_property__current p on u.property_id = p.property_id
)
select * from final
