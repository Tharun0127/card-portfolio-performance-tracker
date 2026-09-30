-- mart_decomposition
-- Splits the Q1 to Q4 spend change of every cell into four effects that add up exactly
-- to the change:  customers, active rate, transactions per active, average ticket.
--
-- Primary method: additive LMDI (logarithmic mean Divisia index).
--     effect_x = L(spend_q4, spend_q1) * ln(x_q4 / x_q1)
--     L(a, b)  = (a - b) / (ln a - ln b), and L(a, a) = a
-- The four logs add up to ln(spend_q4 / spend_q1), so the effects add up to
-- spend_q4 - spend_q1 with no residual and no dependence on factor order.
--
-- LMDI needs every factor to be positive in both periods. If any factor is zero the
-- cell falls back to sequential substitution (change one factor at a time, in the
-- order customers, active rate, transactions per active, average ticket) and is flagged.
-- Sequential effects are also computed for every cell as a cross-check.

with base as (

    select
        *,
        spend_q4 - spend_q1 as delta_spend,
        least(
            n_q1, n_q4,
            active_rate_q1, active_rate_q4,
            txns_per_active_q1, txns_per_active_q4,
            avg_ticket_q1, avg_ticket_q4
        ) > 0 as lmdi_applicable
    from mart_cell_period

),

log_mean as (

    select
        *,
        case
            when not lmdi_applicable then null
            when spend_q4 = spend_q1 then spend_q1
            else (spend_q4 - spend_q1) / (ln(spend_q4) - ln(spend_q1))
        end as log_mean_spend
    from base

),

lmdi as (

    select
        *,
        case when lmdi_applicable then log_mean_spend * ln(n_q4 / n_q1) end                             as lmdi_customers,
        case when lmdi_applicable then log_mean_spend * ln(active_rate_q4 / active_rate_q1) end         as lmdi_active_rate,
        case when lmdi_applicable then log_mean_spend * ln(txns_per_active_q4 / txns_per_active_q1) end as lmdi_txns_per_active,
        case when lmdi_applicable then log_mean_spend * ln(avg_ticket_q4 / avg_ticket_q1) end           as lmdi_avg_ticket
    from log_mean

),

sequential as (

    -- Walk from Q1 to Q4 one factor at a time. Factors already visited are at their
    -- Q4 value, factors not yet visited are still at their Q1 value.
    select
        *,
        (n_q4 - n_q1) * active_rate_q1 * txns_per_active_q1 * avg_ticket_q1                     as seq_customers,
        n_q4 * (active_rate_q4 - active_rate_q1) * txns_per_active_q1 * avg_ticket_q1           as seq_active_rate,
        n_q4 * active_rate_q4 * (txns_per_active_q4 - txns_per_active_q1) * avg_ticket_q1       as seq_txns_per_active,
        n_q4 * active_rate_q4 * txns_per_active_q4 * (avg_ticket_q4 - avg_ticket_q1)            as seq_avg_ticket
    from lmdi

),

chosen as (

    select
        *,
        case when lmdi_applicable then 'lmdi' else 'sequential_fallback' end       as decomposition_method,
        case when lmdi_applicable then lmdi_customers else seq_customers end             as effect_customers,
        case when lmdi_applicable then lmdi_active_rate else seq_active_rate end         as effect_active_rate,
        case when lmdi_applicable then lmdi_txns_per_active else seq_txns_per_active end as effect_txns_per_active,
        case when lmdi_applicable then lmdi_avg_ticket else seq_avg_ticket end           as effect_avg_ticket
    from sequential

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
    active_q1,
    active_q4,
    txns_q1,
    txns_q4,
    spend_q1,
    spend_q4,
    active_rate_q1,
    active_rate_q4,
    txns_per_active_q1,
    txns_per_active_q4,
    avg_ticket_q1,
    avg_ticket_q4,
    delta_spend,
    case when spend_q1 > 0 then delta_spend / spend_q1 end as pct_change,
    decomposition_method,
    effect_customers,
    effect_active_rate,
    effect_txns_per_active,
    effect_avg_ticket,
    -- should be zero up to floating point noise
    effect_customers + effect_active_rate + effect_txns_per_active + effect_avg_ticket
        - delta_spend as residual,
    case greatest(abs(effect_customers), abs(effect_active_rate),
                  abs(effect_txns_per_active), abs(effect_avg_ticket))
        when 0 then 'None'
        when abs(effect_customers) then 'Customers on book'
        when abs(effect_txns_per_active) then 'Transactions per active'
        when abs(effect_avg_ticket) then 'Average ticket'
        when abs(effect_active_rate) then 'Active rate'
    end as dominant_driver,
    lmdi_customers,
    lmdi_active_rate,
    lmdi_txns_per_active,
    lmdi_avg_ticket,
    seq_customers,
    seq_active_rate,
    seq_txns_per_active,
    seq_avg_ticket
from chosen
order by method, scenario, grain, card_tier, tenure_band, attrition_flag
