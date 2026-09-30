-- pbi_dim_customer  (exported as powerbi/dim_customer.csv)
-- One row per customer with descriptive attributes for slicing.

select
    c.customer_id,
    c.attrition_flag,
    seg.card_tier,
    seg.tenure_band,
    seg.card_tier || ' / ' || seg.tenure_band as tier_tenure_cell,
    seg.cell_customers,
    case when seg.is_low_n_cell then 'Low n, not interpreted' else 'OK' end as cell_sample_flag,
    c.months_on_book,
    c.customer_age,
    c.gender,
    c.education_level,
    c.marital_status,
    c.income_category,
    c.relationship_count,
    c.months_inactive_12m,
    c.contacts_12m,
    c.credit_limit
from stg_customers as c
inner join int_customer_segments as seg
    on c.customer_id = seg.customer_id
order by c.customer_id
