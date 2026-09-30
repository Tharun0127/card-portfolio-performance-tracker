-- mart_cell_quarter
-- The four building blocks of the identity, aggregated per quarter at five grains:
-- portfolio, tier, tenure, tier x tenure, and attrition status.
--
--   customers         on book in the quarter
--   active_customers  on book with at least one transaction
--   txns              transactions by on-book customers
--   spend             spend by on-book customers
--
-- fsum is DuckDB's compensated (Kahan) sum. Plain floating point sums depend on the
-- order rows are added up, which would make the SQL vs Python check noisy.

with aggregated as (

    select
        method,
        scenario,
        quarter,
        card_tier,
        tenure_band,
        attrition_flag,
        grouping(card_tier)      as tier_rolled_up,
        grouping(tenure_band)    as tenure_rolled_up,
        grouping(attrition_flag) as attrition_rolled_up,
        count(*) filter (where on_book)                           as customers,
        count(*) filter (where on_book and is_active)             as active_customers,
        coalesce(fsum(txn_count) filter (where on_book), 0.0)     as txns,
        coalesce(fsum(spend) filter (where on_book), 0.0)         as spend
    from int_customer_quarter_scenario
    group by grouping sets (
        (method, scenario, quarter),
        (method, scenario, quarter, card_tier),
        (method, scenario, quarter, tenure_band),
        (method, scenario, quarter, card_tier, tenure_band),
        (method, scenario, quarter, attrition_flag)
    )

)

select
    method,
    scenario,
    case
        when attrition_rolled_up = 0                      then 'attrition'
        when tier_rolled_up = 0 and tenure_rolled_up = 0  then 'tier_x_tenure'
        when tier_rolled_up = 0                           then 'tier'
        when tenure_rolled_up = 0                         then 'tenure'
        else 'portfolio'
    end as grain,
    coalesce(card_tier, 'All')      as card_tier,
    coalesce(tenure_band, 'All')    as tenure_band,
    coalesce(attrition_flag, 'All') as attrition_flag,
    quarter,
    customers,
    active_customers,
    txns,
    spend
from aggregated
order by method, scenario, grain, card_tier, tenure_band, attrition_flag, quarter
