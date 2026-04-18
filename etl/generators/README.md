# Synthetic Inventory Generator

This generator creates a larger, repeatable sample dataset for SkuSense without changing the raw schema that the Glue jobs already expect.

## Why it exists

The original sample file was enough to prove the pipeline shape, but not enough to support:

- warehouse-level trend analysis
- replenishment patterns
- realistic stockout risk examples
- a credible QuickSight dashboard

The generator fixes that by creating daily `product_id + warehouse_id + snapshot_date` history.

## What it generates

- `etl/sample_data/inventory_levels.csv`
  - Raw inventory snapshots used by the AWS pipeline
  - Columns: `product_id`, `warehouse_id`, `qty_on_hand`, `load_dt`
- `etl/sample_data/sku_master.csv`
  - Product reference data for the ETL layer
- `dbt/seeds/product_master.csv`
  - Matching product seed for `dim_product`

## Business logic built into the data

The generator is synthetic, but it is not random noise. It simulates:

- product-level baseline demand
- warehouse-specific demand multipliers
- stable, tight, and volatile inventory profiles
- replenishment orders with lead times
- periodic demand spikes
- stockout and recovery periods

That gives the downstream dbt models enough signal to produce meaningful:

- inventory deltas
- sold proxies
- rolling usage
- days until stockout
- reorder flags
- stock status segmentation

## Usage

Run from the repo root:

```bash
python3 etl/generators/generate_inventory_data.py
```

Useful options:

```bash
python3 etl/generators/generate_inventory_data.py \
  --days 180 \
  --sku-count 75 \
  --warehouse-count 4 \
  --seed 42 \
  --start-date 2025-01-01
```

## Interview-ready explanation

If asked why the project uses synthetic data, the honest answer is:

> Public warehouse-level inventory snapshot datasets are rare, so I generated synthetic daily inventory history with controlled demand and replenishment rules. That let me preserve the true warehouse grain, test my dbt models, and build a realistic BI layer without pretending the source data was real production data.
