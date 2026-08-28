with source as (
    select * from {{ source('raw', 'gl_entries') }}
),

renamed as (
    select
        cast(gl_entry_id as varchar) as gl_entry_id,
        cast(journal_id as varchar) as journal_id,
        cast(property_id as varchar) as property_id,
        cast(posting_date as date) as posting_date,
        upper(trim(cast(account_code as varchar))) as account_code,
        trim(cast(account_name as varchar)) as account_name,
        lower(trim(cast(account_type as varchar))) as account_type,
        cast(debit_amount as decimal(18, 2)) as debit_amount,
        cast(credit_amount as decimal(18, 2)) as credit_amount,
        cast(description as varchar) as entry_description,
        cast(source_system as varchar) as source_system,
        cast(source_record_id as varchar) as source_record_id,
        cast(source_loaded_at as timestamp) as source_loaded_at,
    from source
)
select * from renamed
