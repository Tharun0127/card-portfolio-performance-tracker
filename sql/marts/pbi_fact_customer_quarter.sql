-- pbi_fact_customer_quarter  (exported as powerbi/fact_customer_quarter.csv)
-- Grain: one row per scenario x customer x quarter in which the customer is on book.
-- Base-case (linear) quarterly values only. Off-book rows are not stored, so counting
-- rows counts customers on book. In scenario B the attrited customers have a Q1 row
-- and no Q4 row.

select
    case f.scenario when 'A' then 1 when 'B' then 2 end as scenario_key,
    f.customer_id,
    seg.tier_key,
    seg.tenure_key,
    f.quarter,
    cast(f.is_active as integer) as is_active,
    f.txn_count,
    f.spend
from int_customer_quarter_scenario as f
inner join int_customer_segments as seg
    on f.customer_id = seg.customer_id
where f.method = 'linear'
  and f.on_book
order by scenario_key, f.customer_id, f.quarter
