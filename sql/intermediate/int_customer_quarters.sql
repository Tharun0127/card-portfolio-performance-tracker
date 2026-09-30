-- int_customer_quarters
-- One row per customer x quarterly assumption x quarter (Q1, Q4).
--
-- The file has 12-month totals and Q4/Q1 ratios (r), not quarterly levels.
-- Every assumption below pins down Q1 as  total / (a + b * r)  and Q4 as  r * Q1:
--
--   linear      Q2 and Q3 lie on a straight line between Q1 and Q4.
--               Then Q1 + Q4 = total / 2, so Q1 = total / (2 + 2r).      (base case)
--   early_step  Q2 = Q3 = Q1, the change happens in Q4.
--               total = 3*Q1 + r*Q1, so Q1 = total / (3 + r).            (sensitivity)
--   late_step   Q2 = Q3 = Q4, the change happens right after Q1.
--               total = Q1 + 3*r*Q1, so Q1 = total / (1 + 3r).           (sensitivity)
--
-- See ASSUMPTIONS.md for the derivation and what each one implies.

with assumptions as (

    select * from (values
        ('linear',     2.0, 2.0),
        ('early_step', 3.0, 1.0),
        ('late_step',  1.0, 3.0)
    ) as t (method, a, b)

),

inputs as (

    select
        customer_id,
        total_trans_amt,
        total_trans_ct,
        ct_ratio_q4_q1 as ct_ratio,
        -- A customer with zero Q4 transactions cannot have Q4 spend. Two rows in the
        -- raw file say otherwise (count ratio 0, amount ratio > 0). Count wins.
        case when ct_ratio_q4_q1 = 0 then 0.0 else amt_ratio_q4_q1 end as amt_ratio
    from stg_customers

),

q1 as (

    select
        i.customer_id,
        m.method,
        i.amt_ratio,
        i.ct_ratio,
        i.total_trans_amt / (m.a + m.b * i.amt_ratio) as q1_spend,
        i.total_trans_ct  / (m.a + m.b * i.ct_ratio)  as q1_txns
    from inputs as i
    cross join assumptions as m

),

quarters as (

    select customer_id, method, 'Q1' as quarter, q1_txns as txn_count, q1_spend as spend
    from q1

    union all

    select customer_id, method, 'Q4' as quarter, ct_ratio * q1_txns, amt_ratio * q1_spend
    from q1

)

select
    customer_id,
    method,
    quarter,
    txn_count,
    spend,
    -- Active = at least one transaction in the quarter. The derived count is positive
    -- exactly when the raw data says the customer transacted, whatever the assumption.
    txn_count > 0 as is_active
from quarters
order by method, customer_id, quarter
