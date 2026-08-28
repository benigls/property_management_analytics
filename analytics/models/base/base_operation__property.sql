with stg_operation__property as (
    select * from {{ ref('stg_operation__property') }}
),

final as (
    select *
    from stg_operation__property
    -- Keep identifiable properties with valid active-date ranges.
    where property_id is not null
      and active_from is not null
      and (active_to is null or active_to >= active_from)
)
select * from final
