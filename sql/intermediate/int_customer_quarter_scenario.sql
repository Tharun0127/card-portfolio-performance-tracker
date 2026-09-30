-- int_customer_quarter_scenario
-- One row per customer x assumption x scenario x quarter, with an on_book flag.
--
--   Scenario A, as observed:       the same customers are on book in Q1 and Q4.
--   Scenario B, Q4 exit run-rate:  attrited customers are off book at Q4 end, so they
--                                  are counted in Q1 and removed from Q4.

with scenarios as (

    select * from (values
        ('A', 'As observed'),
        ('B', 'Q4 exit run-rate')
    ) as t (scenario, scenario_name)

)

select
    q.method,
    s.scenario,
    s.scenario_name,
    q.customer_id,
    q.quarter,
    seg.card_tier,
    seg.tenure_band,
    seg.attrition_flag,
    not (s.scenario = 'B' and q.quarter = 'Q4' and seg.is_attrited) as on_book,
    q.is_active,
    q.txn_count,
    q.spend
from int_customer_quarters as q
inner join int_customer_segments as seg
    on q.customer_id = seg.customer_id
cross join scenarios as s
order by q.method, s.scenario, q.customer_id, q.quarter
