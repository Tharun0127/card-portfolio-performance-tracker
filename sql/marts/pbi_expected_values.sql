-- pbi_expected_values  (exported as powerbi/expected_values.csv)
-- Not part of the data model. These are the base-case results from the SQL pipeline,
-- one row per scenario x slicer combination, to check the Power BI measures against
-- after the report is built. tier = 'All' means no tier is selected in the slicer.

select
    scenario,
    card_tier   as tier,
    tenure_band as tenure,
    is_low_n,
    customers_q1,
    customers_q4,
    round(spend_q1, 2)               as spend_q1,
    round(spend_q4, 2)               as spend_q4,
    round(delta_spend, 2)            as spend_change,
    round(pct_change, 6)             as spend_change_pct,
    round(active_rate_q1, 6)         as active_rate_q1,
    round(active_rate_q4, 6)         as active_rate_q4,
    round(txns_per_active_q1, 6)     as txns_per_active_q1,
    round(txns_per_active_q4, 6)     as txns_per_active_q4,
    round(avg_ticket_q1, 6)          as avg_ticket_q1,
    round(avg_ticket_q4, 6)          as avg_ticket_q4,
    round(effect_customers, 2)       as effect_customers,
    round(effect_active_rate, 2)     as effect_active_rate,
    round(effect_txns_per_active, 2) as effect_txns_per_active,
    round(effect_avg_ticket, 2)      as effect_avg_ticket,
    decomposition_method,
    dominant_driver
from mart_decomposition
where method = 'linear'
  and grain in ('portfolio', 'tier', 'tenure', 'tier_x_tenure')
order by
    scenario,
    case grain when 'portfolio' then 1 when 'tier' then 2 when 'tenure' then 3 else 4 end,
    card_tier,
    tenure_band
