with allocated as (
    select charge_id, sum(allocated_amount) as allocated_amount
    from {{ ref('int_payment_allocation__conformed') }}
    where allocation_date <= date '2026-06-30'
    group by 1
)
select
    c.charge_id,
    c.net_charge_amount,
    a.allocated_amount
from {{ ref('int_charge__conformed') }} c
inner join allocated a using (charge_id)
where a.allocated_amount > c.net_charge_amount

