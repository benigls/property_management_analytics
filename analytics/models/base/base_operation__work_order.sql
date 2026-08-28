with stg_operation__work_order as (
    select * from {{ ref('stg_operation__work_order') }}
),
base_operation__vendor as (
    select * from {{ ref('base_operation__vendor') }}
),

final as (
    select w.*
    from stg_operation__work_order w
    -- Keep valid work orders linked to cleaned vendors.
    inner join base_operation__vendor v on w.vendor_id = v.vendor_id
    where w.work_order_id is not null
      and w.opened_at is not null
      and (w.first_response_at is null or w.first_response_at >= w.opened_at)
      and (w.closed_at is null or w.closed_at >= w.opened_at)
      and w.labor_cost >= 0
      and w.material_cost >= 0
      and w.vendor_cost >= 0
)
select * from final
