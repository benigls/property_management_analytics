

with int_charge__conformed as (
    select * from {{ ref('int_charge__conformed') }}
),
int_payment_allocation__conformed as (
    select * from {{ ref('int_payment_allocation__conformed') }}
),
dim_property__current as (
    select * from {{ ref('dim_property__current') }}
),

charge_period as (
    select
        charge_id,
        property_id,
        date_trunc('month', due_date)::date as due_month,
        net_charge_amount,
        approved_credit_amount,
        source_loaded_at,
    from int_charge__conformed
    where charge_type <> 'writeoff'
      and due_date <= {{ analytics_as_of_date() }}
      and posted_at <= {{ analytics_cutoff_timestamp() }}
),
allocated_through_cutoff as (
    select
        charge_id,
        count(*) as allocation_count,
        cast(sum(allocated_amount) as decimal(18, 2)) as allocated_payment_amount
    from int_payment_allocation__conformed
    where allocation_date <= {{ analytics_as_of_date() }}
    group by 1
),
property_month as (
    select
        c.property_id,
        c.due_month,
        count(*) as charge_count,
        sum(coalesce(a.allocation_count, 0)) as allocation_count,
        cast(sum(c.net_charge_amount) as decimal(18, 2)) as charges_net_of_credits,
        cast(sum(c.approved_credit_amount) as decimal(18, 2)) as approved_credit_amount,
        cast(sum(coalesce(a.allocated_payment_amount, 0)) as decimal(18, 2))
            as allocated_payment_amount,
        max(c.source_loaded_at) as source_loaded_at,
    from charge_period c
    left join allocated_through_cutoff a using (charge_id)
    group by 1, 2
)
, final as (
    select
        m.property_id,
        p.property_name,
        p.market_id,
        p.property_class,
        m.due_month as performance_month,
        m.charge_count,
        m.allocation_count,
        m.charges_net_of_credits,
        m.approved_credit_amount,
        m.allocated_payment_amount,
        cast(m.charges_net_of_credits - m.allocated_payment_amount as decimal(18, 2))
            as outstanding_charge_balance,
        cast(
            m.allocated_payment_amount / nullif(m.charges_net_of_credits, 0)
            as decimal(18, 6)
        ) as collection_rate,
        {{ analytics_as_of_date() }} as allocation_cutoff_date,
        m.source_loaded_at,
    from property_month m
    inner join dim_property__current p using (property_id)

)
select * from final
