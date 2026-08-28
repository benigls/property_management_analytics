

with int_payment_allocation__conformed as (
    select * from {{ ref('int_payment_allocation__conformed') }}
),
int_charge__conformed as (
    select * from {{ ref('int_charge__conformed') }}
),
dim_property__current as (
    select * from {{ ref('dim_property__current') }}
),
dim_unit__current as (
    select * from {{ ref('dim_unit__current') }}
),
dim_tenant__current as (
    select * from {{ ref('dim_tenant__current') }}
),

allocated as (
    select charge_id, sum(allocated_amount) as allocated_payment_amount
    from int_payment_allocation__conformed
    where allocation_date <= {{ analytics_as_of_date() }}
    group by 1
),
balances as (
    select
        c.*,
        coalesce(a.allocated_payment_amount, 0::decimal(18, 2)) as allocated_payment_amount,
        cast(c.net_charge_amount - coalesce(a.allocated_payment_amount, 0)
            as decimal(18, 2)) as outstanding_balance,
        greatest(date_diff('day', c.due_date, {{ analytics_as_of_date() }}), 0)::integer
            as days_past_due
    from int_charge__conformed c
    left join allocated a using (charge_id)
    where c.due_date <= {{ analytics_as_of_date() }}
      and c.charge_type = 'rent'
)
, final as (
    select
        b.charge_id,
        b.property_id,
        p.property_name,
        p.market_id,
        p.property_class,
        b.unit_id,
        u.unit_number,
        b.lease_id,
        b.tenant_id,
        t.tenant_name,
        b.due_date,
        b.net_charge_amount,
        b.allocated_payment_amount,
        b.outstanding_balance,
        b.days_past_due,
        case
            when b.days_past_due = 0 then 'current'
            when b.days_past_due <= 30 then '1-30'
            when b.days_past_due <= 60 then '31-60'
            when b.days_past_due <= 90 then '61-90'
            else '90+'
        end as aging_bucket,
        {{ analytics_as_of_date() }} as analytics_as_of_date
    from balances b
    inner join dim_property__current p using (property_id)
    inner join dim_unit__current u using (unit_id, property_id)
    inner join dim_tenant__current t using (tenant_id)
    where b.outstanding_balance > 0
)
select * from final
