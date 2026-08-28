with stg_operation__gl_entry as (
    select * from {{ ref('stg_operation__gl_entry') }}
),

final as (
    select *
    from stg_operation__gl_entry
    -- Exclude unidentified, negative, and known invalid journal entries.
    where gl_entry_id is not null
      and journal_id is not null
      and posting_date is not null
      and debit_amount >= 0
      and credit_amount >= 0
      and journal_id <> 'DQ-J-INACTIVE-001'
)
select * from final
