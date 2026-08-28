
with int_charge__conformed as (
    select * from {{ ref('int_charge__conformed') }}
),
int_payment_allocation__conformed as (
    select * from {{ ref('int_payment_allocation__conformed') }}
),

charge_components as (
    select
        charge_id,
        property_id,
        tenant_id,
        lease_id,
        charge_date,
        due_date,
        case when charge_type = 'writeoff' then 0 else charge_amount end as gross_charge_amount,
        approved_credit_amount,
        writeoff_amount,
        net_charge_amount
    from int_charge__conformed
    where posted_at <= {{ analytics_cutoff_timestamp() }}
      and due_date <= {{ analytics_as_of_date() }}
),
allocations as (
    select
        charge_id,
        sum(allocated_amount) as allocated_payment_amount
    from int_payment_allocation__conformed
    where allocation_date <= {{ analytics_as_of_date() }}
    group by 1
),
charge_balances as (
    select
        c.*,
        coalesce(a.allocated_payment_amount, 0::decimal(18, 2)) as allocated_payment_amount,
        cast(
            c.gross_charge_amount
            - c.approved_credit_amount
            - c.writeoff_amount
            - coalesce(a.allocated_payment_amount, 0::decimal(18, 2))
            as decimal(18, 2)
        ) as ending_ar_balance
    from charge_components c
    left join allocations a using (charge_id)
)
, final as (
    select
        property_id,
        tenant_id,
        lease_id,
        min(charge_date) as first_charge_date,
        max(due_date) as latest_due_date,
        count(*) as charge_count,
        cast(sum(gross_charge_amount) as decimal(18, 2)) as gross_charge_amount,
        cast(sum(approved_credit_amount) as decimal(18, 2)) as approved_credit_amount,
        cast(sum(writeoff_amount) as decimal(18, 2)) as writeoff_amount,
        cast(sum(allocated_payment_amount) as decimal(18, 2)) as allocated_payment_amount,
        cast(sum(ending_ar_balance) as decimal(18, 2)) as ending_ar_balance,
        case
            when abs(
                sum(ending_ar_balance)
                - (
                    sum(gross_charge_amount)
                    - sum(approved_credit_amount)
                    - sum(writeoff_amount)
                    - sum(allocated_payment_amount)
                )
            ) <= 0.01 then 'reconciled'
            else 'unreconciled'
        end as reconciliation_status,
        {{ analytics_as_of_date() }} as reconciliation_as_of_date
    from charge_balances
    group by 1, 2, 3

)
select * from final
