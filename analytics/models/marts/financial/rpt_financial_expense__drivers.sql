

with int_gl_entry__conformed as (
    select * from {{ ref('int_gl_entry__conformed') }}
),
int_budget__conformed as (
    select * from {{ ref('int_budget__conformed') }}
),
dim_property__current as (
    select * from {{ ref('dim_property__current') }}
),

actual as (
    select
        property_id,
        date_trunc('month', posting_date)::date as performance_month,
        account_code,
        account_name,
        cast(sum(debit_amount - credit_amount) as decimal(18, 2)) as actual_expense,
        max(source_loaded_at) as source_loaded_at,
    from int_gl_entry__conformed
    where account_type = 'expense'
      and posting_date <= {{ analytics_as_of_date() }}
    group by 1, 2, 3, 4
),
budget as (
    select
        property_id,
        budget_month as performance_month,
        account_code,
        account_name,
        cast(sum(budget_amount) as decimal(18, 2)) as budget_expense
    from int_budget__conformed
    where account_type = 'expense'
      and budget_month <= {{ analytics_as_of_date() }}
    group by 1, 2, 3, 4
),
combined as (
    select
        coalesce(a.property_id, b.property_id) as property_id,
        coalesce(a.performance_month, b.performance_month) as performance_month,
        coalesce(a.account_code, b.account_code) as account_code,
        coalesce(a.account_name, b.account_name) as account_name,
        coalesce(a.actual_expense, 0::decimal(18, 2)) as actual_expense,
        coalesce(b.budget_expense, 0::decimal(18, 2)) as budget_expense,
        a.source_loaded_at,
    from actual a
    full outer join budget b using (property_id, performance_month, account_code, account_name)
),
with_history as (
    select
        c.*,
        p.property_name,
        p.market_id,
        p.property_class,
        lag(actual_expense, 12) over (
            partition by c.property_id, c.account_code order by c.performance_month
        ) as prior_year_actual_expense
    from combined c
    inner join dim_property__current p using (property_id)
)
, final as (
    select
        *,
        cast(budget_expense - actual_expense as decimal(18, 2)) as expense_favorable_variance,
        cast(actual_expense - prior_year_actual_expense as decimal(18, 2))
            as expense_year_over_year_change,
        cast(
            (actual_expense - prior_year_actual_expense)
            / nullif(abs(prior_year_actual_expense), 0)
            as decimal(18, 6)
        ) as expense_year_over_year_change_rate
    from with_history

)
select * from final
