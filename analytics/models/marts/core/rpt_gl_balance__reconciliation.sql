
with int_gl_entry__conformed as (
    select * from {{ ref('int_gl_entry__conformed') }}
),

final as (
    select
        journal_id,
        property_id,
        posting_date,
        count(*) as entry_count,
        cast(sum(debit_amount) as decimal(18, 2)) as total_debit_amount,
        cast(sum(credit_amount) as decimal(18, 2)) as total_credit_amount,
        cast(sum(debit_amount) - sum(credit_amount) as decimal(18, 2)) as balance_difference,
        case
            when abs(sum(debit_amount) - sum(credit_amount)) <= 0.01 then 'balanced'
            else 'unbalanced'
        end as reconciliation_status
    from int_gl_entry__conformed
    group by 1, 2, 3

)
select * from final
