

with int_work_order__conformed as (
    select * from {{ ref('int_work_order__conformed') }}
),
int_work_order_status__history as (
    select * from {{ ref('int_work_order_status__history') }}
),
int_work_order__performance as (
    select * from {{ ref('int_work_order__performance') }}
),

close_events as (
    select
        prior.unit_id,
        prior.category,
        prior.work_order_id as prior_work_order_id,
        h.event_at as prior_closed_at
    from int_work_order__conformed prior
    inner join int_work_order_status__history h using (work_order_id)
    where prior.maintenance_type <> 'preventive'
      and h.work_order_status = 'closed'
),
matched as (
    select
        current.work_order_id,
        current.property_id,
        current.property_name,
        current.unit_id,
        current.unit_number,
        current.category,
        current.priority,
        current.opened_at,
        current.valid_closed_at,
        current.total_cost,
        prior.prior_work_order_id,
        prior.prior_closed_at,
        row_number() over (
            partition by current.work_order_id
            order by prior.prior_closed_at desc, prior.prior_work_order_id
        ) as prior_event_rank
    from int_work_order__performance current
    inner join close_events prior
        on current.unit_id = prior.unit_id
        and current.category = prior.category
        and current.work_order_id <> prior.prior_work_order_id
        and prior.prior_closed_at < current.opened_at
        and prior.prior_closed_at >= current.opened_at - interval 90 days
    where current.maintenance_type <> 'preventive'
)
, final as (
    select
        work_order_id,
        property_id,
        property_name,
        unit_id,
        unit_number,
        category,
        priority,
        opened_at,
        valid_closed_at,
        total_cost,
        prior_work_order_id,
        prior_closed_at,
        date_diff('day', prior_closed_at, opened_at) as days_since_prior_close,
        count(*) over (partition by property_id, unit_id, category) as recurring_event_count,
        sum(total_cost) over (partition by property_id, unit_id, category) as recurring_event_cost
    from matched
    where prior_event_rank = 1

)
select * from final
