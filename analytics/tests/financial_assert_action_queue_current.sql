with expected as (
    select max(performance_month) as latest_month, count(distinct property_id) as property_count
    from {{ ref('rpt_financial_property__monthly') }}
),
actual as (
    select min(performance_month) as min_month, max(performance_month) as max_month,
        count(*) as row_count, count(distinct property_id) as property_count,
        min(review_rank) as min_rank, max(review_rank) as max_rank
    from {{ ref('rpt_financial_action__queue') }}
)
select *
from expected cross join actual
where min_month <> latest_month
   or max_month <> latest_month
   or actual.property_count <> expected.property_count
   or row_count <> expected.property_count
   or min_rank <> 1
   or max_rank <> expected.property_count

