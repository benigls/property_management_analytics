

with int_lease__conformed as (
    select * from {{ ref('int_lease__conformed') }}
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

signed_successors as (
    select
        renewal_of_lease_id as prior_lease_id,
        min(lease_start_date) as successor_start_date,
        min_by(lease_id, lease_start_date) as successor_lease_id,
        min_by(tenant_id, lease_start_date) as successor_tenant_id,
        min(signed_date) as successor_signed_date
    from int_lease__conformed
    where renewal_of_lease_id is not null
      and signed_date <= {{ analytics_as_of_date() }}
    group by 1
),
horizon as (
    select
        l.*,
        s.successor_lease_id,
        s.successor_tenant_id,
        s.successor_start_date,
        s.successor_signed_date
    from int_lease__conformed l
    left join signed_successors s on l.lease_id = s.prior_lease_id
    where l.lease_start_date <= {{ analytics_as_of_date() }}
      and l.lease_end_date > {{ analytics_as_of_date() }}
      and l.lease_end_date <= {{ analytics_forecast_end_date() }}
)
, final as (
    select
        h.lease_id,
        h.property_id,
        p.property_name,
        p.market_id,
        p.property_class,
        h.unit_id,
        u.unit_number,
        h.tenant_id,
        t.tenant_name,
        h.lease_end_date as expiration_date,
        date_trunc('month', h.lease_end_date)::date as expiration_month,
        date_diff('day', {{ analytics_as_of_date() }}, h.lease_end_date)::integer as days_to_expiration,
        h.monthly_rent as contractual_monthly_rent,
        case
            when h.successor_lease_id is null then 'unmitigated'
            when h.successor_tenant_id = h.tenant_id then 'signed_renewal'
            else 'signed_replacement'
        end as mitigation_status,
        h.successor_lease_id,
        h.successor_start_date,
        h.successor_signed_date,
        h.successor_lease_id is not null as is_mitigated,
        case when h.successor_lease_id is null then h.monthly_rent else 0::decimal(18, 2) end
            as unmitigated_rent_exposure,
        {{ analytics_as_of_date() }} as analytics_as_of_date
    from horizon h
    inner join dim_property__current p using (property_id)
    inner join dim_unit__current u using (unit_id, property_id)
    inner join dim_tenant__current t using (tenant_id)
)
select * from final
