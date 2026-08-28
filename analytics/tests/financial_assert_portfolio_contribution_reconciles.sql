select
    performance_month,
    sum(noi) as property_noi,
    max(portfolio_noi) as portfolio_noi,
    sum(noi_portfolio_contribution) as contribution_total
from {{ ref('rpt_financial_portfolio__contribution') }}
group by 1
having abs(sum(noi) - max(portfolio_noi)) > 0.01
    or abs(sum(noi_portfolio_contribution) - 1) > 0.0001

