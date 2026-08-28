with stg_operation__payment as (
    select * from {{ ref('stg_operation__payment') }}
),

final as (
    select *
    from stg_operation__payment
    -- Keep identifiable payments with dates and non-negative amounts.
    where payment_id is not null
      and payment_date is not null
      and payment_amount >= 0
)
select * from final
