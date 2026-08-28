with stg_operation__unit as (
    select * from {{ ref('stg_operation__unit') }}
),

final as (
    select *
    from stg_operation__unit
    -- Keep identifiable units with valid dates and non-negative rent.
    where unit_id is not null
      and active_from is not null
      and (active_to is null or active_to >= active_from)
      and market_rent >= 0
)
select * from final
