
with int_payment_allocation__conformed as (
    select * from {{ ref('int_payment_allocation__conformed') }}
),
int_payment__conformed as (
    select * from {{ ref('int_payment__conformed') }}
),

allocated as (
    select
        payment_id,
        sum(allocated_amount) as allocated_amount
    from int_payment_allocation__conformed
    where allocation_date <= {{ analytics_as_of_date() }}
    group by 1
)
, final as (
    select
        p.payment_id,
        p.property_id,
        p.tenant_id,
        p.payment_date,
        p.payment_amount,
        coalesce(a.allocated_amount, 0::decimal(18, 2)) as allocated_amount,
        cast(p.payment_amount - coalesce(a.allocated_amount, 0::decimal(18, 2)) as decimal(18, 2))
            as unapplied_amount,
        case
            when coalesce(a.allocated_amount, 0) <= p.payment_amount then 'reconciled'
            else 'overallocated'
        end as reconciliation_status,
        {{ analytics_as_of_date() }} as reconciliation_as_of_date
    from int_payment__conformed p
    left join allocated a using (payment_id)
    where p.payment_status = 'posted'
      and p.posted_at <= {{ analytics_cutoff_timestamp() }}

)
select * from final
