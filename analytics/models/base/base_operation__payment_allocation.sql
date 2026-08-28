with stg_operation__payment_allocation as (
    select * from {{ ref('stg_operation__payment_allocation') }}
),
base_operation__payment as (
    select * from {{ ref('base_operation__payment') }}
),
base_operation__charge as (
    select * from {{ ref('base_operation__charge') }}
),

final as (
    select a.*
    from stg_operation__payment_allocation a
    -- Keep valid allocations linked to cleaned payments and charges.
    inner join base_operation__payment p on a.payment_id = p.payment_id
    inner join base_operation__charge c
        on a.charge_id = c.charge_id
        and p.property_id = c.property_id
        and p.tenant_id = c.tenant_id
    where a.payment_allocation_id is not null
      and a.allocated_amount >= 0
      and a.allocation_date is not null
)
select * from final
