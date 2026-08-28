with stg_operation__charge as (
    select * from {{ ref('stg_operation__charge') }}
),

deduplicated as (
    -- Remove exact duplicates before charges reach financial models.
    select distinct *
    from stg_operation__charge
), final as (
    select *
    from deduplicated
    -- Keep dated charges with internally valid credit and amount values.
    where charge_id is not null
      and charge_date is not null
      and due_date is not null
      and posted_at is not null
      and approved_credit_amount >= 0
      and approved_credit_amount <= abs(charge_amount)
      and (charge_type = 'writeoff' or charge_amount >= 0)
)
select * from final
