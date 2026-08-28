
with dates as (
    select cast(date_day as date) as date_day
    from generate_series(
        {{ analytics_history_start_date() }},
        {{ analytics_forecast_end_date() }},
        interval 1 day
    ) as generated(date_day)
)
, final as (
    select
        date_day as date_key,
        extract(year from date_day)::integer as calendar_year,
        extract(quarter from date_day)::integer as calendar_quarter,
        extract(month from date_day)::integer as month_number,
        monthname(date_day) as month_name,
        date_trunc('month', date_day)::date as month_start_date,
        last_day(date_day)::date as month_end_date,
        extract(isodow from date_day)::integer as iso_day_of_week,
        extract(isodow from date_day) in (6, 7) as is_weekend,
        date_day = {{ analytics_as_of_date() }} as is_analytics_cutoff
    from dates

)
select * from final
