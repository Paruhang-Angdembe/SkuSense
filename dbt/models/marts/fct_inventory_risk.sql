{{ config(
    materialized = 'table',
    tags = ['marts', 'fact', 'inventory_risk']
) }}

select
    cast(snapshot_date as date) as snapshot_date,
    cast(product_id as varchar) as product_id,
    cast(warehouse_id as varchar) as warehouse_id,
    cast(qty_on_hand as bigint) as qty_on_hand,
    cast(prev_qty_on_hand as bigint) as prev_qty_on_hand,
    cast(inventory_delta as bigint) as inventory_delta,
    cast(daily_units_sold_proxy as bigint) as daily_units_sold_proxy,
    cast(received_units as bigint) as received_units,
    cast(avg_daily_usage_7d as double) as avg_daily_usage_7d,
    cast(days_until_stockout as double) as days_until_stockout,
    cast(reorder_flag as boolean) as reorder_flag,
    cast(stock_status as varchar) as stock_status
from {{ ref('int_inventory_risk') }}
-- Why this shape:

-- fact stays at the exact grain you defined: one row per snapshot_date, product_id, warehouse_id
-- it exposes business metrics from int_inventory_risk without redoing logic
-- dims will connect on product_id, warehouse_id, and snapshot_date