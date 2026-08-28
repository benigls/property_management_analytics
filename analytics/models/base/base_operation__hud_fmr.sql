with stg_operation__hud_fmr as (
    select * from {{ ref('stg_operation__hud_fmr') }}
),

final as (
    select *
    from stg_operation__hud_fmr
    -- Keep benchmark records with valid market, bedroom, year, and rent values.
    where market_id is not null
      and bedrooms >= 0
      and fiscal_year > 0
      and fmr_amount >= 0
)
select * from final
