with base_charge as (
    select * from {{ ref('base_operation__charge') }}
),

leases as (
    select * from {{ ref('int_lease__conformed') }}
),

final as (
    select
        c.charge_id,
        c.property_id,
        c.unit_id,
        c.lease_id,
        c.tenant_id,
        c.charge_date,
        c.due_date,
        c.charge_type,
        c.charge_amount,
        c.approved_credit_amount,
        case when c.charge_type = 'writeoff' then abs(c.charge_amount) else 0::decimal(18, 2) end
            as writeoff_amount,
        case
            when c.charge_type = 'writeoff' then 0::decimal(18, 2)
            else c.charge_amount - c.approved_credit_amount
        end as net_charge_amount,
        c.posted_at,
        c.source_system,
        c.source_record_id,
        c.source_loaded_at,
    from base_charge as c
    inner join leases as l
        on c.lease_id = l.lease_id
        and c.tenant_id = l.tenant_id
        and c.unit_id = l.unit_id
)
select * from final
