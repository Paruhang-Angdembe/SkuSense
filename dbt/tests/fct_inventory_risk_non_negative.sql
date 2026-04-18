select *
from {{ ref('fct_inventory_risk') }}
where qty_on_hand < 0
   or coalesce(daily_units_sold_proxy, 0) < 0
   or coalesce(received_units, 0) < 0
   or coalesce(avg_daily_usage_7d, 0) < 0
   or coalesce(days_until_stockout, 0) < 0

-- catches impossible negative values in the core metrics