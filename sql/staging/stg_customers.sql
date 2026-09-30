-- stg_customers
-- One row per customer. Reads the raw Kaggle file, drops the two leaked
-- Naive_Bayes_Classifier columns, and renames everything to snake_case.
-- No business logic here: values are passed through unchanged.

with source as (

    select columns(c -> not starts_with(c, 'Naive_Bayes_Classifier'))
    from read_csv(getvariable('raw_csv_path'), header = true)

),

renamed as (

    select
        cast(CLIENTNUM as bigint)               as customer_id,
        Attrition_Flag                          as attrition_flag,
        Attrition_Flag = 'Attrited Customer'    as is_attrited,
        Card_Category                           as card_tier,
        cast(Months_on_book as integer)         as months_on_book,

        -- 12-month totals and Q4/Q1 ratios: the only spend information in the file
        cast(Total_Trans_Amt as double)         as total_trans_amt,
        cast(Total_Trans_Ct as double)          as total_trans_ct,
        cast(Total_Amt_Chng_Q4_Q1 as double)    as amt_ratio_q4_q1,
        cast(Total_Ct_Chng_Q4_Q1 as double)     as ct_ratio_q4_q1,

        -- descriptive attributes, used only as dashboard slicers
        cast(Customer_Age as integer)           as customer_age,
        Gender                                  as gender,
        cast(Dependent_count as integer)        as dependent_count,
        Education_Level                         as education_level,
        Marital_Status                          as marital_status,
        Income_Category                         as income_category,
        cast(Total_Relationship_Count as integer) as relationship_count,
        cast(Months_Inactive_12_mon as integer) as months_inactive_12m,
        cast(Contacts_Count_12_mon as integer)  as contacts_12m,
        cast(Credit_Limit as double)            as credit_limit,
        cast(Total_Revolving_Bal as double)     as revolving_balance,
        cast(Avg_Utilization_Ratio as double)   as avg_utilization_ratio
    from source

)

select * from renamed
order by customer_id
