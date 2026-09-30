-- pbi_dim_tenure  (exported as powerbi/dim_tenure.csv)
-- One row per tenure band. tenure_key doubles as the sort order (newest first).

select
    tenure_key,
    tenure_band,
    min(months_on_book) as min_months_on_book,
    max(months_on_book) as max_months_on_book,
    count(*)            as customers
from int_customer_segments
group by tenure_key, tenure_band
order by tenure_key
