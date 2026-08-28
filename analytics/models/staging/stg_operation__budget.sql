with source as (
    select * from {{ source('raw', 'budgets') }}
),

renamed as (
    select
        cast(budget_id as varchar) as budget_id,
        cast(property_id as varchar) as property_id,
        date_trunc('month', cast(budget_month as date))::date as budget_month,
        upper(trim(cast(account_code as varchar))) as account_code,
        trim(cast(account_name as varchar)) as account_name,
        lower(trim(cast(account_type as varchar))) as account_type,
        cast(budget_amount as decimal(18, 2)) as budget_amount,
        cast(source_system as varchar) as source_system,
        cast(source_record_id as varchar) as source_record_id,
        cast(source_loaded_at as timestamp) as source_loaded_at,
    from source
)
select * from renamed
