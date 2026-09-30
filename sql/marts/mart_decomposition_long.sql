-- mart_decomposition_long
-- One row per cell x factor: the shape a waterfall chart needs.
-- Window functions add, per cell:
--   share_of_change   the factor's effect as a share of the cell's spend change
--   effect_rank       1 = largest effect in absolute size (the dominant driver)
--   bridge_start/end  running position of the bar, starting from Q1 spend

with unpivoted as (

    select method, scenario, grain, card_tier, tenure_band, attrition_flag, segment,
           is_low_n, decomposition_method, spend_q1, spend_q4, delta_spend,
           1 as factor_order, 'Customers on book' as factor, effect_customers as effect
    from mart_decomposition

    union all

    select method, scenario, grain, card_tier, tenure_band, attrition_flag, segment,
           is_low_n, decomposition_method, spend_q1, spend_q4, delta_spend,
           2, 'Active rate', effect_active_rate
    from mart_decomposition

    union all

    select method, scenario, grain, card_tier, tenure_band, attrition_flag, segment,
           is_low_n, decomposition_method, spend_q1, spend_q4, delta_spend,
           3, 'Transactions per active', effect_txns_per_active
    from mart_decomposition

    union all

    select method, scenario, grain, card_tier, tenure_band, attrition_flag, segment,
           is_low_n, decomposition_method, spend_q1, spend_q4, delta_spend,
           4, 'Average ticket', effect_avg_ticket
    from mart_decomposition

),

windowed as (

    select
        *,
        case when delta_spend <> 0 then effect / delta_spend end as share_of_change,
        case when spend_q1 > 0 then effect / spend_q1 end        as effect_pct_of_q1_spend,
        row_number() over cell_by_size                           as effect_rank,
        spend_q1 + sum(effect) over cell_in_order                as bridge_end
    from unpivoted
    window
        cell_by_size as (
            partition by method, scenario, grain, card_tier, tenure_band, attrition_flag
            order by abs(effect) desc, factor_order
        ),
        cell_in_order as (
            partition by method, scenario, grain, card_tier, tenure_band, attrition_flag
            order by factor_order
            rows between unbounded preceding and current row
        )

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
    decomposition_method,
    factor_order,
    factor,
    effect,
    share_of_change,
    effect_pct_of_q1_spend,
    effect_rank,
    bridge_end - effect as bridge_start,
    bridge_end
from windowed
order by method, scenario, grain, card_tier, tenure_band, attrition_flag, factor_order
