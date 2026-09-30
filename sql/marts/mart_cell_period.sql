-- mart_cell_period
-- One row per cell with Q1 and Q4 side by side, plus the four factors of the identity
--
--   spend = customers x active_rate x txns_per_active x avg_ticket
--
-- Suffix _q1 is the base period, _q4 is the comparison period.
-- A ratio with a zero denominator is stored as 0, which makes the identity still hold
-- (spend is 0 in that case) and marks the cell for the sequential fallback.

with pivoted as (

    select
        method,
        scenario,
        grain,
        card_tier,
        tenure_band,
        attrition_flag,
        max(customers)        filter (where quarter = 'Q1') as customers_q1,
        max(customers)        filter (where quarter = 'Q4') as customers_q4,
        max(active_customers) filter (where quarter = 'Q1') as active_q1,
        max(active_customers) filter (where quarter = 'Q4') as active_q4,
        max(txns)             filter (where quarter = 'Q1') as txns_q1,
        max(txns)             filter (where quarter = 'Q4') as txns_q4,
        max(spend)            filter (where quarter = 'Q1') as spend_q1,
        max(spend)            filter (where quarter = 'Q4') as spend_q4
    from mart_cell_quarter
    group by method, scenario, grain, card_tier, tenure_band, attrition_flag

),

factors as (

    select
        *,
        cast(customers_q1 as double) as n_q1,
        cast(customers_q4 as double) as n_q4,
        case when customers_q1 > 0 then active_q1 / customers_q1 else 0.0 end as active_rate_q1,
        case when customers_q4 > 0 then active_q4 / customers_q4 else 0.0 end as active_rate_q4,
        case when active_q1 > 0 then txns_q1 / active_q1 else 0.0 end         as txns_per_active_q1,
        case when active_q4 > 0 then txns_q4 / active_q4 else 0.0 end         as txns_per_active_q4,
        case when txns_q1 > 0 then spend_q1 / txns_q1 else 0.0 end            as avg_ticket_q1,
        case when txns_q4 > 0 then spend_q4 / txns_q4 else 0.0 end            as avg_ticket_q4
    from pivoted

)

select
    method,
    scenario,
    grain,
    card_tier,
    tenure_band,
    attrition_flag,
    case grain
        when 'portfolio'     then 'Portfolio'
        when 'tier'          then card_tier
        when 'tenure'        then tenure_band || ' months'
        when 'tier_x_tenure' then card_tier || ' / ' || tenure_band
        when 'attrition'     then attrition_flag
    end as segment,
    customers_q1,
    customers_q4,
    active_q1,
    active_q4,
    txns_q1,
    txns_q4,
    spend_q1,
    spend_q4,
    n_q1,
    n_q4,
    active_rate_q1,
    active_rate_q4,
    txns_per_active_q1,
    txns_per_active_q4,
    avg_ticket_q1,
    avg_ticket_q4,
    -- Low n is judged on the Q1 book so the flag is the same in both scenarios.
    customers_q1 < getvariable('low_n_threshold') as is_low_n
from factors
order by method, scenario, grain, card_tier, tenure_band, attrition_flag
