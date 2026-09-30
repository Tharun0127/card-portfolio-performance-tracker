-- mart_segment_contribution
-- How much of the portfolio spend change each segment explains.
-- Segments within a grain are mutually exclusive and cover the whole book, so their
-- spend changes add up to the portfolio change and the shares add up to 100%.
--
--   share_of_portfolio_change  segment change / portfolio change
--   contribution_pts           segment change / portfolio Q1 spend, in fractions.
--                              Summed over segments this equals the portfolio % change.
--   over_index                 share of change / share of Q1 spend. Above 1 means the
--                              segment explains more of the change than its size suggests.

with segments as (

    select *
    from mart_decomposition
    where grain <> 'portfolio'

),

with_totals as (

    select
        *,
        sum(spend_q1)     over grain_total as portfolio_spend_q1,
        sum(delta_spend)  over grain_total as portfolio_delta_spend,
        sum(customers_q1) over grain_total as portfolio_customers_q1
    from segments
    window grain_total as (partition by method, scenario, grain)

),

shares as (

    select
        *,
        customers_q1 / portfolio_customers_q1 as share_of_customers_q1,
        spend_q1 / portfolio_spend_q1         as share_of_spend_q1,
        delta_spend / portfolio_delta_spend   as share_of_portfolio_change,
        delta_spend / portfolio_spend_q1      as contribution_pts
    from with_totals

)

select
    method,
    scenario,
    grain,
    card_tier,
    tenure_band,
    attrition_flag,
    segment,
    is_low_n,
    customers_q1,
    customers_q4,
    spend_q1,
    spend_q4,
    delta_spend,
    pct_change,
    share_of_customers_q1,
    share_of_spend_q1,
    share_of_portfolio_change,
    contribution_pts,
    share_of_portfolio_change / share_of_spend_q1 as over_index,
    rank() over (
        partition by method, scenario, grain
        order by abs(delta_spend) desc
    ) as contribution_rank,
    sum(share_of_portfolio_change) over (
        partition by method, scenario, grain
        order by abs(delta_spend) desc, segment
        rows between unbounded preceding and current row
    ) as cumulative_share_of_change,
    dominant_driver,
    decomposition_method,
    effect_customers,
    effect_active_rate,
    effect_txns_per_active,
    effect_avg_ticket
from shares
order by method, scenario, grain, contribution_rank, segment
