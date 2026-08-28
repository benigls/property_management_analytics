with base_budget as (
    select * from {{ ref('base_operation__budget') }}
),

final as (
    select
        b.budget_id,
        b.property_id,
        b.budget_month,
        b.account_code,
        b.account_name,
        b.account_type,
        b.budget_amount,
        b.source_system,
        b.source_record_id,
        b.source_loaded_at,
    from base_budget as b
)
select * from final
