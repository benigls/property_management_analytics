

with rpt_gl_balance__reconciliation as (
    select * from {{ ref('rpt_gl_balance__reconciliation') }}
),
rpt_ar_balance__reconciliation as (
    select * from {{ ref('rpt_ar_balance__reconciliation') }}
),
rpt_payment_allocation__reconciliation as (
    select * from {{ ref('rpt_payment_allocation__reconciliation') }}
),
int_gl_entry__conformed as (
    select * from {{ ref('int_gl_entry__conformed') }}
),
int_payment__conformed as (
    select * from {{ ref('int_payment__conformed') }}
),
int_charge__conformed as (
    select * from {{ ref('int_charge__conformed') }}
),
rpt_financial_property__monthly as (
    select * from {{ ref('rpt_financial_property__monthly') }}
),
rpt_financial_collections__monthly as (
    select * from {{ ref('rpt_financial_collections__monthly') }}
),

gl_check as (
    select
        count(*) as checked_row_count,
        count(*) filter (where reconciliation_status <> 'balanced') as exception_count,
        coalesce(sum(abs(balance_difference)), 0) as difference_amount
    from rpt_gl_balance__reconciliation
),
ar_check as (
    select
        count(*) as checked_row_count,
        count(*) filter (where reconciliation_status <> 'reconciled') as exception_count,
        coalesce(sum(
            abs(
                ending_ar_balance
                - (gross_charge_amount - approved_credit_amount - writeoff_amount - allocated_payment_amount)
            )
        ), 0) as difference_amount
    from rpt_ar_balance__reconciliation
),
payment_check as (
    select
        count(*) as checked_row_count,
        count(*) filter (where reconciliation_status <> 'reconciled') as exception_count,
        coalesce(sum(case when unapplied_amount < 0 then abs(unapplied_amount) else 0 end), 0)
            as difference_amount
    from rpt_payment_allocation__reconciliation
),
cash_gl as (
    select coalesce(sum(debit_amount), 0) as cash_receipt_amount
    from int_gl_entry__conformed
    where account_code = 'ASSET_CASH'
      and posting_date <= {{ analytics_as_of_date() }}
),
posted_payments as (
    select coalesce(sum(payment_amount), 0) as posted_payment_amount
    from int_payment__conformed
    where payment_status = 'posted'
      and posted_at <= {{ analytics_cutoff_timestamp() }}
),
cash_check as (
    select
        2 as checked_row_count,
        case when abs(g.cash_receipt_amount - p.posted_payment_amount) <= 0.01
            then 0 else 1 end as exception_count,
        abs(g.cash_receipt_amount - p.posted_payment_amount) as difference_amount
    from cash_gl g cross join posted_payments p
),
ar_control as (
    select coalesce(sum(debit_amount - credit_amount), 0) as ending_ar_control_amount
    from int_gl_entry__conformed
    where account_code = 'ASSET_AR'
      and posting_date <= {{ analytics_as_of_date() }}
),
ar_components as (
    select
        (select coalesce(sum(ending_ar_balance), 0) from rpt_ar_balance__reconciliation)
        + (
            select coalesce(sum(credit_amount - debit_amount), 0)
            from int_gl_entry__conformed
            where account_code = 'REV_OTHER'
              and posting_date <= {{ analytics_as_of_date() }}
        ) as expected_ar_control_amount
),
ar_control_check as (
    select
        2 as checked_row_count,
        case when abs(c.ending_ar_control_amount - e.expected_ar_control_amount) <= 0.01
            then 0 else 1 end as exception_count,
        abs(c.ending_ar_control_amount - e.expected_ar_control_amount) as difference_amount
    from ar_control c cross join ar_components e
),
rental_gl as (
    select coalesce(sum(credit_amount - debit_amount), 0) as rental_revenue_amount
    from int_gl_entry__conformed
    where account_code = 'REV_RENT'
      and posting_date <= {{ analytics_as_of_date() }}
),
curated_rent_charges as (
    select coalesce(sum(net_charge_amount), 0) as curated_charge_amount
    from int_charge__conformed
    where charge_type = 'rent'
      and posted_at <= {{ analytics_cutoff_timestamp() }}
),
rental_revenue_check as (
    select
        3 as checked_row_count,
        case when abs(g.rental_revenue_amount - c.curated_charge_amount)
            <= 0.01 then 0 else 1 end as exception_count,
        abs(g.rental_revenue_amount - c.curated_charge_amount)
            as difference_amount
    from rental_gl g cross join curated_rent_charges c
),
source_actual as (
    select
        sum(credit_amount - debit_amount) filter (where account_type = 'revenue') as revenue,
        sum(debit_amount - credit_amount) filter (where account_type = 'expense') as expense
    from int_gl_entry__conformed
    where posting_date <= {{ analytics_as_of_date() }}
),
mart_actual as (
    select sum(operating_revenue) as revenue, sum(operating_expense) as expense
    from rpt_financial_property__monthly
),
actual_check as (
    select
        2 as checked_row_count,
        case when abs(s.revenue - m.revenue) <= 0.01 and abs(s.expense - m.expense) <= 0.01
            then 0 else 1 end as exception_count,
        abs(s.revenue - m.revenue) + abs(s.expense - m.expense) as difference_amount
    from source_actual s cross join mart_actual m
),
collection_check as (
    select
        count(*) as checked_row_count,
        count(*) filter (where collection_rate < 0 or collection_rate > 1) as exception_count,
        coalesce(sum(greatest(0, allocated_payment_amount - charges_net_of_credits)), 0)
            as difference_amount
    from rpt_financial_collections__monthly
),
checks as (
    select 'gl_journal_balance' as check_id, * from gl_check
    union all select 'ar_subledger_balance', * from ar_check
    union all select 'payment_allocation_control', * from payment_check
    union all select 'cash_receipts_to_payments', * from cash_check
    union all select 'ar_control_account', * from ar_control_check
    union all select 'rental_revenue_to_charges', * from rental_revenue_check
    union all select 'financial_mart_to_gl', * from actual_check
    union all select 'collection_rate_bounds', * from collection_check
)
, final as (
    select
        check_id,
        checked_row_count,
        exception_count,
        cast(difference_amount as decimal(18, 2)) as difference_amount,
        case when exception_count = 0 and abs(difference_amount) <= 0.01 then 'pass' else 'fail' end
            as check_status,
        case check_id
            when 'gl_journal_balance' then 'Every source journal must balance debits to credits.'
            when 'ar_subledger_balance' then 'AR must equal charges less credits, write-offs, and allocations.'
            when 'payment_allocation_control' then 'Posted payments must not be overallocated.'
            when 'cash_receipts_to_payments' then 'GL cash receipts must equal posted source payments.'
            when 'ar_control_account' then 'The GL AR control must equal rent AR plus other-income AR.'
            when 'rental_revenue_to_charges' then 'GL rent revenue must equal cleaned source charges.'
            when 'financial_mart_to_gl' then 'Financial mart actuals must reconcile to the conformed GL.'
            when 'collection_rate_bounds' then 'Allocated collections cannot exceed eligible net charges.'
        end as check_detail,
        {{ analytics_as_of_date() }} as reconciliation_as_of_date
    from checks
)
select * from final
