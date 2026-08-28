with stg_operation__budget as (
    select * from {{ ref('stg_operation__budget') }}
),

final as (
    select *
    from stg_operation__budget
    -- Keep identifiable budgets with valid periods and amounts.
    where budget_id is not null
      and budget_month is not null
      and budget_amount >= 0
)
select * from final
