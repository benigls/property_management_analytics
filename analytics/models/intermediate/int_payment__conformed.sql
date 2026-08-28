with base_payment as (
    select * from {{ ref('base_operation__payment') }}
),

final as (
    select
        pmt.payment_id,
        pmt.property_id,
        pmt.tenant_id,
        pmt.payment_date,
        pmt.payment_amount,
        pmt.payment_status,
        pmt.posted_at,
        pmt.source_system,
        pmt.source_record_id,
        pmt.source_loaded_at,
    from base_payment as pmt
)
select * from final
