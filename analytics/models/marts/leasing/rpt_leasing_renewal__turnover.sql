

with int_lease__conformed as (
    select * from {{ ref('int_lease__conformed') }}
),
dim_property__current as (
    select * from {{ ref('dim_property__current') }}
),

completed_expirations as (
    select
        lease_id,
        property_id,
        unit_id,
        tenant_id,
        lease_end_date,
        monthly_rent,
        lease_outcome
    from int_lease__conformed
    where lease_end_date <= {{ analytics_as_of_date() }}
      and lease_outcome in ('renewed', 'turned_over')
),
linked_successors as (
    select
        renewal_of_lease_id as prior_lease_id,
        min(lease_start_date) as successor_start_date,
        min_by(lease_id, lease_start_date) as successor_lease_id,
        min_by(tenant_id, lease_start_date) as successor_tenant_id
    from int_lease__conformed
    where renewal_of_lease_id is not null
    group by 1
)
, final as (
    select
        l.lease_id,
        l.property_id,
        p.property_name,
        p.market_id,
        p.property_class,
        l.unit_id,
        l.tenant_id,
        l.lease_end_date,
        date_trunc('month', l.lease_end_date)::date as expiration_month,
        l.monthly_rent,
        l.lease_outcome,
        s.successor_lease_id,
        s.successor_start_date,
        s.successor_tenant_id,
        s.successor_lease_id is not null as has_explicit_successor,
        l.lease_outcome = 'renewed'
            and s.successor_lease_id is not null
            and s.successor_tenant_id = l.tenant_id as is_renewal,
        l.lease_outcome = 'turned_over'
            and s.successor_lease_id is not null
            and s.successor_tenant_id <> l.tenant_id as is_turnover,
        {{ analytics_as_of_date() }} as analytics_as_of_date
    from completed_expirations l
    inner join dim_property__current p using (property_id)
    left join linked_successors s on l.lease_id = s.prior_lease_id
)
select * from final
