with stg_operation__tenant as (
    select * from {{ ref('stg_operation__tenant') }}
),

final as (
    select *
    from stg_operation__tenant
    -- Keep tenants with required identity and creation fields.
    where tenant_id is not null
      and created_date is not null
)
select * from final
