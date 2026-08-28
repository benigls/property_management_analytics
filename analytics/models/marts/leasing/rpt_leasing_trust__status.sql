

with rpt_ar_balance__reconciliation as (
    select * from {{ ref('rpt_ar_balance__reconciliation') }}
),
int_lease__conformed as (
    select * from {{ ref('int_lease__conformed') }}
),

ar as (
    select
        count(*) filter (where reconciliation_status <> 'reconciled') as failed_count,
        count(*) as checked_count
    from rpt_ar_balance__reconciliation
),
source as (
    select max(source_loaded_at) as source_loaded_at from int_lease__conformed
)
, final as (
    select
        'ar_reconciliation' as check_id,
        'Tenant balance reconciliation' as check_label,
        case when failed_count = 0 then 'pass' else 'fail' end as check_status,
        checked_count::integer as check_value,
        concat(checked_count, ' tenant/lease balances checked; ', failed_count, ' unreconciled.')
            as detail,
        {{ analytics_as_of_date() }} as analytics_as_of_date
    from ar
    union all
    select
        'source_freshness',
        'Synthetic source cutoff',
        case when source_loaded_at::date = {{ analytics_as_of_date() }} then 'pass' else 'warning' end,
        1,
        concat('Latest synthetic lease source loaded ', source_loaded_at, '.'),
        {{ analytics_as_of_date() }}
    from source
)
select * from final
