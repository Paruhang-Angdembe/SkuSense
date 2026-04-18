{{ config(
    materialized = 'view',
    tags = ['staging', 'silver']
) }}

with source as (

    select
        product_id,
        warehouse_id,
        load_dt,
        qty_on_hand
    from {{ source('skusense_silver', 'inventory_silver') }}

),

cleaned as (

    select
        trim(product_id) as product_id,
        trim(warehouse_id) as warehouse_id,
        trim(load_dt) as load_dt,
        qty_on_hand
    from source
    where product_id is not null
      and warehouse_id is not null
      and load_dt is not null
      and trim(load_dt) <> ''
      and qty_on_hand is not null

),


renamed as (

    select
        cast(product_id as varchar) as product_id,
        cast(warehouse_id as varchar) as warehouse_id,
        cast(date_parse(load_dt, '%c/%e/%Y') as date) as snapshot_date,
        cast(qty_on_hand as bigint) as qty_on_hand
    from cleaned

)

select * from renamed
