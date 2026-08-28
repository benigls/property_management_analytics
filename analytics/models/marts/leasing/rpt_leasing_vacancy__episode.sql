

with int_lease__conformed as (
    select * from {{ ref('int_lease__conformed') }}
),
dim_property__current as (
    select * from {{ ref('dim_property__current') }}
),

lease_sequence as (
    select
        l.*,
        lead(lease_id) over (partition by unit_id order by lease_start_date, lease_id)
            as next_lease_id,
        lead(lease_start_date) over (partition by unit_id order by lease_start_date, lease_id)
            as next_lease_start_date
    from int_lease__conformed l
),
completed_episodes as (
    select
        *,
        lease_end_date + interval 1 day as vacancy_start_date,
        next_lease_start_date - interval 1 day as vacancy_end_date,
        date_diff('day', lease_end_date + interval 1 day, next_lease_start_date)::integer
            as vacancy_days
    from lease_sequence
    where lease_outcome = 'turned_over'
      and lease_end_date <= {{ analytics_as_of_date() }}
      and next_lease_start_date <= {{ analytics_as_of_date() }}
      and next_lease_start_date > lease_end_date
)
, final as (
    select
        concat(lease_id, ':', next_lease_id) as vacancy_episode_id,
        property_id,
        p.property_name,
        p.market_id,
        p.property_class,
        unit_id,
        lease_id as prior_lease_id,
        next_lease_id,
        vacancy_start_date::date as vacancy_start_date,
        vacancy_end_date::date as vacancy_end_date,
        vacancy_days,
        {{ analytics_as_of_date() }} as analytics_as_of_date
    from completed_episodes
    inner join dim_property__current p using (property_id)
)
select * from final
