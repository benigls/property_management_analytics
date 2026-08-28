

with int_gl_entry__conformed as (
    select * from {{ ref('int_gl_entry__conformed') }}
),
int_budget__conformed as (
    select * from {{ ref('int_budget__conformed') }}
),
dim_property__current as (
    select * from {{ ref('dim_property__current') }}
),

actual_by_month as (
    select
        property_id,
        date_trunc('month', posting_date)::date as performance_month,
        cast(sum(credit_amount - debit_amount) filter (where account_type = 'revenue') as decimal(18, 2))
            as operating_revenue,
        cast(sum(debit_amount - credit_amount) filter (where account_type = 'expense') as decimal(18, 2))
            as operating_expense,
        max(source_loaded_at) as source_loaded_at,
    from int_gl_entry__conformed
    where account_type in ('revenue', 'expense')
      and posting_date <= {{ analytics_as_of_date() }}
    group by 1, 2
),
budget_by_month as (
    select
        property_id,
        budget_month as performance_month,
        cast(sum(budget_amount) filter (where account_type = 'revenue') as decimal(18, 2))
            as budget_revenue,
        cast(sum(budget_amount) filter (where account_type = 'expense') as decimal(18, 2))
            as budget_expense,
    from int_budget__conformed
    where budget_month <= {{ analytics_as_of_date() }}
    group by 1, 2
),
joined as (
    select
        coalesce(a.property_id, b.property_id) as property_id,
        coalesce(a.performance_month, b.performance_month) as performance_month,
        coalesce(a.operating_revenue, 0::decimal(18, 2)) as operating_revenue,
        coalesce(a.operating_expense, 0::decimal(18, 2)) as operating_expense,
        coalesce(b.budget_revenue, 0::decimal(18, 2)) as budget_revenue,
        coalesce(b.budget_expense, 0::decimal(18, 2)) as budget_expense,
        a.source_loaded_at,
    from actual_by_month a
    full outer join budget_by_month b using (property_id, performance_month)
),
metrics as (
    select
        j.property_id,
        p.property_name,
        p.market_id,
        p.property_class,
        p.stated_unit_count,
        j.performance_month,
        j.operating_revenue,
        j.operating_expense,
        cast(j.operating_revenue - j.operating_expense as decimal(18, 2)) as noi,
        cast(
            (j.operating_revenue - j.operating_expense) / nullif(j.operating_revenue, 0)
            as decimal(18, 6)
        ) as noi_margin,
        j.budget_revenue,
        j.budget_expense,
        cast(j.budget_revenue - j.budget_expense as decimal(18, 2)) as budget_noi,
        cast(j.operating_revenue - j.budget_revenue as decimal(18, 2))
            as revenue_favorable_variance,
        cast(j.budget_expense - j.operating_expense as decimal(18, 2))
            as expense_favorable_variance,
        cast(
            (j.operating_revenue - j.operating_expense)
            - (j.budget_revenue - j.budget_expense)
            as decimal(18, 2)
        ) as noi_favorable_variance,
        j.source_loaded_at,
    from joined j
    inner join dim_property__current p using (property_id)
),
with_history as (
    select
        *,
        lag(noi, 1) over (partition by property_id order by performance_month) as prior_month_noi,
        lag(noi, 12) over (partition by property_id order by performance_month) as prior_year_noi,
        lag(operating_revenue, 12) over (partition by property_id order by performance_month)
            as prior_year_operating_revenue,
        lag(operating_expense, 12) over (partition by property_id order by performance_month)
            as prior_year_operating_expense
    from metrics
)
, final as (
    select
        *,
        cast(noi - prior_month_noi as decimal(18, 2)) as noi_month_over_month_change,
        cast(noi - prior_year_noi as decimal(18, 2)) as noi_year_over_year_change,
        cast(operating_revenue - prior_year_operating_revenue as decimal(18, 2))
            as revenue_year_over_year_change,
        cast(operating_expense - prior_year_operating_expense as decimal(18, 2))
            as expense_year_over_year_change
    from with_history

)
select * from final
