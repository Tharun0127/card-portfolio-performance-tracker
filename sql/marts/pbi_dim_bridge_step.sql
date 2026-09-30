-- pbi_dim_bridge_step  (exported as powerbi/dim_bridge_step.csv)
-- Disconnected helper table: the categories on the waterfall axis. It has no
-- relationship to the fact table. The [Bridge Value] measure reads the selected step.

select * from (values
    (1, 'Q1 spend'),
    (2, 'Customers on book'),
    (3, 'Active rate'),
    (4, 'Transactions per active'),
    (5, 'Average ticket')
) as t (step_key, step)
order by step_key
