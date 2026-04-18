{{ config(
    materialized = 'table',
    tags = ['marts', 'dimension', 'date']
) }}

with distinct_dates as (

    select distinct
        snapshot_date as date_day
    from {{ ref('stg_inventory_silver') }}
    where snapshot_date is not null

)

select
    cast(date_day as date) as date_day,
    year(date_day) as year_num,
    quarter(date_day) as quarter_num,
    month(date_day) as month_num,
    date_format(date_day, '%M') as month_name,
    week(date_day) as week_num,
    day(date_day) as day_of_month,
    day_of_week(date_day) as day_of_week_num
from distinct_dates
