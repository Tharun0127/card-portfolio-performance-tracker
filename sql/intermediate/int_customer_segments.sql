-- int_customer_segments
-- One row per customer with its segment: card tier x tenure band.
-- Window functions attach the size of each tier and each tier x tenure cell to the
-- customer row, so the low-n flag travels with the customer into every later table.

with banded as (

    select
        customer_id,
        attrition_flag,
        is_attrited,
        card_tier,
        months_on_book,
        case
            when months_on_book <= 24 then '13-24'
            when months_on_book <= 36 then '25-36'
            when months_on_book <= 48 then '37-48'
            else '49+'
        end as tenure_band
    from stg_customers

),

keyed as (

    select
        *,
        case card_tier
            when 'Blue' then 1
            when 'Silver' then 2
            when 'Gold' then 3
            when 'Platinum' then 4
        end as tier_key,
        case tenure_band
            when '13-24' then 1
            when '25-36' then 2
            when '37-48' then 3
            when '49+' then 4
        end as tenure_key
    from banded

),

sized as (

    select
        *,
        count(*) over (partition by card_tier)              as tier_customers,
        count(*) over (partition by tenure_band)            as tenure_customers,
        count(*) over (partition by card_tier, tenure_band) as cell_customers
    from keyed

)

select
    *,
    cell_customers < getvariable('low_n_threshold') as is_low_n_cell
from sized
order by customer_id
