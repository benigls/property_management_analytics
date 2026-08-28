

with int_gl_entry__conformed as (
    select * from {{ ref('int_gl_entry__conformed') }}
),
dim_property__current as (
    select * from {{ ref('dim_property__current') }}
),

final as (
    select
        g.gl_entry_id,
        g.journal_id,
        g.property_id,
        p.property_name,
        g.posting_date,
        date_trunc('month', g.posting_date)::date as performance_month,
        g.account_code,
        g.account_name,
        g.account_type,
        cast(
            case
                when g.account_type = 'revenue' then g.credit_amount - g.debit_amount
                else g.debit_amount - g.credit_amount
            end as decimal(18, 2)
        ) as actual_amount,
        g.entry_description,
        g.source_system,
        g.source_record_id,
        g.source_loaded_at,
    from int_gl_entry__conformed g
    inner join dim_property__current p using (property_id)
    where g.account_type in ('revenue', 'expense')
      and g.posting_date <= {{ analytics_as_of_date() }}

)
select * from final
