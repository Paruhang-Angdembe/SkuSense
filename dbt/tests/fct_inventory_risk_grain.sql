select
    snapshot_date,
    product_id,
    warehouse_id,
    count(*) as row_count
from {{ ref('fct_inventory_risk') }}
group by 1, 2, 3
having count(*) > 1

-- fails if your fact table violates the intended grain
-- this is the most important custom test in th project