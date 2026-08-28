with base_gl_entry as (
    select * from {{ ref('base_operation__gl_entry') }}
),

final as (
    select
        g.gl_entry_id,
        g.journal_id,
        g.property_id,
        g.posting_date,
        g.account_code,
        g.account_name,
        g.account_type,
        g.debit_amount,
        g.credit_amount,
        g.entry_description,
        g.source_system,
        g.source_record_id,
        g.source_loaded_at,
    from base_gl_entry as g
)
select * from final
