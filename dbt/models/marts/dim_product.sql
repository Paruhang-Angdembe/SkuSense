{{ config(
    materialized = 'table',
    tags = ['marts', 'dimension', 'product']
) }}

select
    cast(product_id as varchar) as product_id,
    cast(product_name as varchar) as product_name,
    cast(category as varchar) as category
from {{ ref('product_master') }}
