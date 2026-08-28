with base_lease as (
    select * from {{ ref('base_operation__lease') }}
),

final as (
    select
        l.lease_id,
        l.property_id,
        l.unit_id,
        l.tenant_id,
        l.lease_start_date,
        l.lease_end_date,
        l.move_in_date,
        l.move_out_date,
        l.signed_date,
        l.monthly_rent,
        l.renewal_of_lease_id,
        l.lease_outcome,
        l.source_system,
        l.source_record_id,
        l.source_loaded_at,
    from base_lease as l
)
select * from final
