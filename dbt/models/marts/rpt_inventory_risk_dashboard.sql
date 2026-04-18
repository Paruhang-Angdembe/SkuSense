{{ config(
    materialized = 'table',
    tags = ['marts', 'reporting', 'dashboard']
) }}

with enriched as (
    select
        concat(cast(f.snapshot_date as varchar), '|', f.product_id, '|', f.warehouse_id) as warehouse_product_snapshot_key,
        f.snapshot_date,
        d.year_num,
        d.quarter_num,
        d.month_num,
        d.month_name,
        d.week_num,
        d.day_of_month,
        d.day_of_week_num,
        f.product_id,
        p.product_name,
        p.category,
        f.warehouse_id,
        w.warehouse_name,
        f.qty_on_hand,
        f.prev_qty_on_hand,
        f.inventory_delta,
        f.daily_units_sold_proxy,
        f.received_units,
        f.avg_daily_usage_7d,
        f.days_until_stockout,
        f.reorder_flag,
        f.stock_status,
        case
            when f.snapshot_date = max(f.snapshot_date) over () then true
            else false
        end as is_latest_snapshot,
        case
            when f.stock_status in ('CRITICAL', 'LOW') then true
            else false
        end as at_risk_flag,
        case
            when f.qty_on_hand = 0 then true
            else false
        end as zero_inventory_flag,
        case
            when coalesce(f.prev_qty_on_hand, 0) > 0 and f.qty_on_hand = 0 then true
            else false
        end as stockout_event_flag,
        case
            when coalesce(f.received_units, 0) > 0 then true
            else false
        end as replenishment_event_flag,
        case
            when f.days_until_stockout is null then 'No usage signal'
            when f.days_until_stockout <= 3 then '0-3 days'
            when f.days_until_stockout <= 7 then '4-7 days'
            when f.days_until_stockout <= 14 then '8-14 days'
            when f.days_until_stockout <= 30 then '15-30 days'
            else '31+ days'
        end as stockout_horizon_bucket,
        case f.stock_status
            when 'CRITICAL' then 1
            when 'LOW' then 2
            when 'MEDIUM' then 3
            else 4
        end as stock_status_sort_order,
        case
            when f.qty_on_hand = 0 then 100
            when f.days_until_stockout is null then 5
            when f.days_until_stockout <= 3 then 95
            when f.days_until_stockout <= 7 then 85
            when f.days_until_stockout <= 14 then 70
            when f.days_until_stockout <= 30 then 40
            else 15
        end as risk_priority_score
    from {{ ref('fct_inventory_risk') }} f
    left join {{ ref('dim_product') }} p
        on f.product_id = p.product_id
    left join {{ ref('dim_warehouse') }} w
        on f.warehouse_id = w.warehouse_id
    left join {{ ref('dim_date') }} d
        on f.snapshot_date = d.date_day
),

ranked as (
    select
        *,
        case
            when risk_priority_score >= 90 then 'P1 - Immediate'
            when risk_priority_score >= 70 then 'P2 - Urgent'
            when risk_priority_score >= 40 then 'P3 - Watch'
            else 'P4 - Healthy'
        end as risk_priority_band,
        case
            when is_latest_snapshot then row_number() over (
                partition by snapshot_date
                order by
                    risk_priority_score desc,
                    coalesce(days_until_stockout, 999999) asc,
                    qty_on_hand asc,
                    product_id asc,
                    warehouse_id asc
            )
        end as latest_rank_overall,
        case
            when is_latest_snapshot then row_number() over (
                partition by snapshot_date, warehouse_id
                order by
                    risk_priority_score desc,
                    coalesce(days_until_stockout, 999999) asc,
                    qty_on_hand asc,
                    product_id asc
            )
        end as latest_rank_in_warehouse
    from enriched
)

select
    warehouse_product_snapshot_key,
    snapshot_date,
    year_num,
    quarter_num,
    month_num,
    month_name,
    week_num,
    day_of_month,
    day_of_week_num,
    product_id,
    product_name,
    category,
    warehouse_id,
    warehouse_name,
    qty_on_hand,
    prev_qty_on_hand,
    inventory_delta,
    daily_units_sold_proxy,
    received_units,
    avg_daily_usage_7d,
    days_until_stockout,
    reorder_flag,
    stock_status,
    stock_status_sort_order,
    is_latest_snapshot,
    at_risk_flag,
    zero_inventory_flag,
    stockout_event_flag,
    replenishment_event_flag,
    stockout_horizon_bucket,
    risk_priority_score,
    risk_priority_band,
    latest_rank_overall,
    latest_rank_in_warehouse
from ranked
