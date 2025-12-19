{{ config(
    materialized = 'view',
    tags = ['staging', 'silver']
)}}

with source as (
    select 
        product_id,
        warehouse_id,
        load_dt,
        qty_on_hand,
        avg_daily_usage,
        days_until_stockout,
        turnover_ratio,
        reorder_flag,
        stock_status

    from {{ source('skusense_silver', 'INVENTORY_SILVER_VW') }}
),

renamed as (
    select
        product_id as product_id,
        warehouse_id as warehouse_id,
        load_dt as snapshot_date,
        qty_on_hand::number as qty_on_hand,
        avg_daily_usage::number as avg_daily_usage,
        days_until_stockout::number as days_until_stockout,
        turnover_ratio::number as turnover_ratio,
        reorder_flag::boolean as reorder_flag,
        stock_status::string as stock_status
    from source

)

select * from renamed