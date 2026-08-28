

with rpt_leasing_expiration__exposure as (
    select * from {{ ref('rpt_leasing_expiration__exposure') }}
),
rpt_leasing_delinquency__current as (
    select * from {{ ref('rpt_leasing_delinquency__current') }}
),

expiration_actions as (
    select
        concat('expiration:', lease_id) as action_id,
        'lease_expiration' as action_type,
        property_id,
        property_name,
        unit_id,
        unit_number,
        lease_id,
        tenant_id,
        tenant_name,
        expiration_date as action_date,
        unmitigated_rent_exposure as financial_exposure,
        days_to_expiration as age_or_days_to_event,
        cast(
            unmitigated_rent_exposure
            + greatest(0, 365 - days_to_expiration) * 5
            as decimal(18, 2)
        ) as priority_score,
        case
            when days_to_expiration <= 90 or unmitigated_rent_exposure >= 2500 then 'high'
            when days_to_expiration <= 180 then 'medium'
            else 'standard'
        end as priority_tier,
        concat(
            'Unmitigated ', strftime(expiration_date, '%Y-%m-%d'),
            ' expiration; contractual monthly rent $',
            format('{:,.2f}', unmitigated_rent_exposure)
        ) as evidence,
        'Start renewal outreach or replacement-leasing action.' as recommended_action,
        analytics_as_of_date
    from rpt_leasing_expiration__exposure
    where mitigation_status = 'unmitigated'
),
tenant_balances as (
    select
        property_id,
        property_name,
        unit_id,
        unit_number,
        lease_id,
        tenant_id,
        tenant_name,
        min(due_date) as oldest_due_date,
        sum(outstanding_balance)::decimal(18, 2) as outstanding_balance,
        max(days_past_due)::integer as oldest_days_past_due,
        string_agg(distinct aging_bucket, ', ' order by aging_bucket) as aging_buckets,
        max(analytics_as_of_date) as analytics_as_of_date
    from rpt_leasing_delinquency__current
    group by 1, 2, 3, 4, 5, 6, 7
),
delinquency_actions as (
    select
        concat('delinquency:', tenant_id, ':', lease_id) as action_id,
        'tenant_delinquency' as action_type,
        property_id,
        property_name,
        unit_id,
        unit_number,
        lease_id,
        tenant_id,
        tenant_name,
        oldest_due_date as action_date,
        outstanding_balance as financial_exposure,
        oldest_days_past_due as age_or_days_to_event,
        cast(outstanding_balance + oldest_days_past_due * 10 as decimal(18, 2))
            as priority_score,
        case
            when oldest_days_past_due > 90 or outstanding_balance >= 3000 then 'high'
            when oldest_days_past_due > 30 or outstanding_balance >= 1500 then 'medium'
            else 'standard'
        end as priority_tier,
        concat(
            'Outstanding rent $', format('{:,.2f}', outstanding_balance),
            '; oldest item ', oldest_days_past_due, ' days past due; buckets ', aging_buckets
        ) as evidence,
        'Review ledger evidence and prioritize collection outreach.' as recommended_action,
        analytics_as_of_date
    from tenant_balances
)
, final as (
    select * from expiration_actions
    union all by name
    select * from delinquency_actions
)
select * from final
