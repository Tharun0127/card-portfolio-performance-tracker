-- pbi_dim_scenario  (exported as powerbi/dim_scenario.csv)

select * from (values
    (1, 'A', 'As observed',
     'Same customers on book in Q1 and Q4. Shows behaviour change only.'),
    (2, 'B', 'Q4 exit run-rate',
     'Attrited customers are off book at Q4 end. Shows the book the team starts next year with.')
) as t (scenario_key, scenario_code, scenario_name, scenario_description)
order by scenario_key
