select 1 as planted_scenario_missing
where not exists (
    select 1
    from {{ ref('rpt_leasing_expiration__exposure') }}
    where property_id = 'PHX-B02'
      and mitigation_status = 'unmitigated'
      and expiration_date <= date '2026-09-30'
    group by property_id
    having count(*) >= 40
)
