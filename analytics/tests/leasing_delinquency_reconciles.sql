with mart_balance as (
    select property_id, tenant_id, lease_id, sum(outstanding_balance) as balance
    from {{ ref('rpt_leasing_delinquency__current') }}
    group by 1, 2, 3
),
reconciled_balance as (
    select property_id, tenant_id, lease_id, sum(ending_ar_balance) as balance
    from {{ ref('rpt_ar_balance__reconciliation') }}
    group by 1, 2, 3
)
select
    coalesce(m.property_id, r.property_id) as property_id,
    coalesce(m.tenant_id, r.tenant_id) as tenant_id,
    coalesce(m.lease_id, r.lease_id) as lease_id,
    coalesce(m.balance, 0) as mart_balance,
    coalesce(r.balance, 0) as reconciled_balance
from mart_balance m
full join reconciled_balance r using (property_id, tenant_id, lease_id)
where abs(coalesce(m.balance, 0) - greatest(coalesce(r.balance, 0), 0)) > 0.01

