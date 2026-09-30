-- mart_mix_reconciliation
-- The portfolio-level decomposition uses portfolio-wide averages. Adding up the
-- tier x tenure cell decompositions gives the same total change but slightly different
-- effects per factor, because portfolio averages also move when the mix of segments
-- shifts. This table puts the two side by side. The gap per factor is the mix effect
-- hidden inside the portfolio-level numbers. The gaps add up to zero.

with portfolio as (

    select method, scenario, factor_order, factor, effect as portfolio_level_effect
    from mart_decomposition_long
    where grain = 'portfolio'

),

cells as (

    select method, scenario, factor_order, factor, fsum(effect) as sum_of_cell_effects
    from mart_decomposition_long
    where grain = 'tier_x_tenure'
    group by method, scenario, factor_order, factor

)

select
    p.method,
    p.scenario,
    p.factor_order,
    p.factor,
    p.portfolio_level_effect,
    c.sum_of_cell_effects,
    p.portfolio_level_effect - c.sum_of_cell_effects as mix_gap
from portfolio as p
inner join cells as c
    on  p.method = c.method
    and p.scenario = c.scenario
    and p.factor_order = c.factor_order
order by p.method, p.scenario, p.factor_order
