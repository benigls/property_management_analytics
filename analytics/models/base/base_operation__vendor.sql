with stg_operation__vendor as (
    select * from {{ ref('stg_operation__vendor') }}
),

final as (
    select *
    from stg_operation__vendor
    -- Keep identifiable vendors with valid active-date ranges.
    where vendor_id is not null
      and active_from is not null
      and (active_to is null or active_to >= active_from)
)
select * from final
