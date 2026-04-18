{{ config(
    materialized = 'table',
    tags = ['marts', 'dimension', 'warehouse']
) }}

select distinct
    cast(warehouse_id as varchar) as warehouse_id,
    cast(warehouse_id as varchar) as warehouse_name
from {{ ref('stg_inventory_silver') }}
where warehouse_id is not null
