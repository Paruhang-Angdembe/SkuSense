-- Goal of this model:
-- take the clean siler snapshot and compute business logic in dbt sql;
-- previous qty, 
-- inventory change,
-- sold proxy,
-- received quantity,
-- 7-day average usage,
-- days until stockout,
-- reorder flag,
-- stock status


{{
    config(
        materialized = "view",
        tags = ['intermediate', 'inventory_risk']
    )
}}

with base as(
    select
        product_id,
        warehouse_id, 
        snapshot_date,
        qty_on_hand
        from {{ref('stg_inventory_silver')}}
),

with_previous as (
    select 
        product_id, 
        warehouse_id,
        snapshot_date,
        qty_on_hand,
        lag(qty_on_hand) over (
            partition by product_id, warehouse_id order by snapshot_date
        ) as prev_qty_on_hand
    from base
),
-- lag gives previous inventory at the same product_id + warehouse_id

with_deltas as (
    select 
       product_id,
        warehouse_id,
        snapshot_date,
        qty_on_hand,
        prev_qty_on_hand,
        qty_on_hand - prev_qty_on_hand as inventory_delta,
        case
            when prev_qty_on_hand is null then 0
            when qty_on_hand - prev_qty_on_hand < 0 then abs(qty_on_hand - prev_qty_on_hand)
            else 0
        end as daily_units_sold_proxy,
        case
            when prev_qty_on_hand is null then 0
            when qty_on_hand - prev_qty_on_hand > 0 then qty_on_hand - prev_qty_on_hand
            else 0
        end as received_units
    from with_previous
),
-- negative delta means inventory likely slow down
-- positive delta means inventory likely received new stock

with_usage as (

    select
        product_id,
        warehouse_id,
        snapshot_date,
        qty_on_hand,
        prev_qty_on_hand,
        inventory_delta,
        daily_units_sold_proxy,
        received_units,
        avg(daily_units_sold_proxy) over (
            partition by product_id, warehouse_id
            order by snapshot_date
            rows between 6 preceding and current row
        ) as avg_daily_usage_7d
    from with_deltas

),

final as (

    select
        product_id,
        warehouse_id,
        snapshot_date,
        qty_on_hand,
        prev_qty_on_hand,
        inventory_delta,
        daily_units_sold_proxy,
        received_units,
        avg_daily_usage_7d,
        case
            when avg_daily_usage_7d > 0 then qty_on_hand / avg_daily_usage_7d
            else null
        end as days_until_stockout,
        case
            when avg_daily_usage_7d > 0 and qty_on_hand / avg_daily_usage_7d <= 14 then true
            else false
        end as reorder_flag,
        case
            when avg_daily_usage_7d is null or avg_daily_usage_7d = 0 then 'HEALTHY'
            when qty_on_hand / avg_daily_usage_7d <= 7 then 'CRITICAL'
            when qty_on_hand / avg_daily_usage_7d <= 14 then 'LOW'
            when qty_on_hand / avg_daily_usage_7d <= 30 then 'MEDIUM'
            else 'HEALTHY'
        end as stock_status
    from with_usage

)

-- rolling 7-days average creates a usuable stickout metric without inventing a new source
-- stock_status and reorder_flag are now visible SQL, which is what you need

select * from final