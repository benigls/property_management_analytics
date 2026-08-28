with base_operation__payment_allocation as (
    select * from {{ ref('base_operation__payment_allocation') }}
),
int_payment__conformed as (
    select * from {{ ref('int_payment__conformed') }}
),
int_charge__conformed as (
    select * from {{ ref('int_charge__conformed') }}
),

final as (
    select
        a.payment_allocation_id,
        a.payment_id,
        a.charge_id,
        c.property_id,
        c.unit_id,
        c.lease_id,
        c.tenant_id,
        a.allocated_amount,
        a.allocation_date,
        a.source_system,
        a.source_record_id,
        a.source_loaded_at,
    from base_operation__payment_allocation a
    inner join int_payment__conformed p on a.payment_id = p.payment_id
    inner join int_charge__conformed c
        on a.charge_id = c.charge_id
        and p.property_id = c.property_id
        and p.tenant_id = c.tenant_id
)
select * from final
