with stg_operation__lease as (
    select * from {{ ref('stg_operation__lease') }}
),

valid_leases as (
    select *
    from stg_operation__lease
    -- Keep identifiable leases with valid dates and non-negative rent.
    where lease_id is not null
      and lease_start_date is not null
      and lease_end_date >= lease_start_date
      and (move_out_date is null or move_in_date is null or move_out_date >= move_in_date)
      and monthly_rent >= 0
), final as (
    select l.*
    from valid_leases l
    -- Keep the earliest lease when valid periods overlap for a unit.
    where not exists (
        select 1
        from valid_leases other
        where other.unit_id = l.unit_id
          and other.lease_id <> l.lease_id
          and other.lease_start_date < l.lease_end_date
          and other.lease_end_date > l.lease_start_date
          and (
              other.lease_start_date < l.lease_start_date
              or (other.lease_start_date = l.lease_start_date and other.lease_id < l.lease_id)
          )
    )
)
select * from final
