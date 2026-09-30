-- pbi_dim_tier  (exported as powerbi/dim_tier.csv)
-- One row per card tier. tier_key doubles as the sort order (entry tier first).

select
    tier_key,
    card_tier,
    count(*) as customers,
    case
        when count(*) < 200 then 'Small sample (' || count(*) || ' customers)'
        else 'OK'
    end as sample_note
from int_customer_segments
group by tier_key, card_tier
order by tier_key
