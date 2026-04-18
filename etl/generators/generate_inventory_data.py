#!/usr/bin/env python3
"""Generate synthetic inventory snapshots for the SkuSense demo pipeline.

The generator creates daily product-by-warehouse inventory snapshots with:
- repeatable output via a random seed
- stable and volatile demand patterns
- warehouse-level demand variation
- replenishment orders with lead times
- occasional demand spikes and stockout periods

Outputs match the current raw sample schema used by Glue:
product_id, warehouse_id, qty_on_hand, load_dt
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


DATE_FORMAT = "%-m/%-d/%Y"

CATEGORY_BLUEPRINTS = {
    "beauty": {
        "names": [
            "Hydrating Face Serum",
            "Gentle Foaming Cleanser",
            "Brightening Eye Cream",
            "Daily Barrier Moisturizer",
            "Nourishing Sheet Mask",
            "Vitamin C Night Cream",
            "Soothing Micellar Water",
            "Balancing Toner Mist",
            "Repair Lip Treatment",
            "SPF 50 Day Lotion",
        ],
        "demand": (3, 8),
    },
    "grocery": {
        "names": [
            "Organic Jasmine Rice",
            "Dark Roast Coffee Pods",
            "Whole Grain Fusilli",
            "Stoneground Oatmeal",
            "Roasted Almond Granola",
            "Extra Virgin Olive Oil",
            "Sea Salt Crackers",
            "Chili Garlic Noodles",
            "Maple Protein Bars",
            "Sparkling Lime Water",
        ],
        "demand": (5, 14),
    },
    "electronics": {
        "names": [
            "Wireless Earbuds",
            "Portable SSD 1TB",
            "Smart Mechanical Keyboard",
            "Bluetooth Desk Lamp",
            "Compact 4K Webcam",
            "USB-C Docking Station",
            "Noise-Canceling Headset",
            "Portable Power Bank",
            "Wi-Fi Smart Plug",
            "Ergonomic Vertical Mouse",
        ],
        "demand": (1, 5),
    },
    "sports": {
        "names": [
            "Non-Slip Yoga Mat",
            "Insulated Water Bottle",
            "Performance Resistance Band",
            "Trail Running Belt",
            "Recovery Foam Roller",
            "Training Jump Rope",
            "Grip Strength Trainer",
            "Lightweight Gym Bag",
            "Core Balance Disc",
            "Cooling Sports Towel",
        ],
        "demand": (2, 7),
    },
    "health": {
        "names": [
            "Kids Multivitamin",
            "Daily Whey Protein",
            "Advanced Omega Capsules",
            "Immune Support Gummies",
            "Complete Electrolyte Mix",
            "Sleep Support Tablets",
            "Collagen Peptide Powder",
            "Magnesium Recovery Drink",
            "Vitamin D Softgels",
            "Probiotic Digestive Blend",
        ],
        "demand": (2, 6),
    },
    "home": {
        "names": [
            "Ceramic Chef Knife",
            "Modern Storage Bin",
            "Stackable Laundry Basket",
            "Stainless Pan Set",
            "Foldable Step Stool",
            "Glass Meal Prep Set",
            "Bamboo Cutting Board",
            "Soft-Close Trash Can",
            "Cordless Table Lamp",
            "Vacuum Storage Bags",
        ],
        "demand": (1, 4),
    },
}

WAREHOUSE_PROFILES = [
    {"warehouse_id": "WH01", "multiplier": 1.20, "variability": 0.16},
    {"warehouse_id": "WH02", "multiplier": 1.00, "variability": 0.12},
    {"warehouse_id": "WH03", "multiplier": 0.82, "variability": 0.18},
    {"warehouse_id": "WH04", "multiplier": 1.35, "variability": 0.22},
    {"warehouse_id": "WH05", "multiplier": 0.68, "variability": 0.20},
]


@dataclass(frozen=True)
class Product:
    product_id: str
    product_name: str
    category: str
    base_daily_demand: int
    volatility: float
    reorder_cover_days: int
    target_cover_days: int
    lead_time_days: int
    spike_chance: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic SkuSense inventory history.")
    parser.add_argument("--days", type=int, default=120, help="Number of daily snapshots to generate.")
    parser.add_argument("--sku-count", type=int, default=50, help="Number of SKUs to create.")
    parser.add_argument(
        "--warehouse-count",
        type=int,
        default=4,
        help="Number of warehouses to include. Max supported by built-in profiles is 5.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for repeatable output.")
    parser.add_argument(
        "--start-date",
        type=lambda value: date.fromisoformat(value),
        default=date(2025, 1, 1),
        help="First snapshot date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--inventory-output",
        type=Path,
        default=Path("etl/sample_data/inventory_levels.csv"),
        help="Output CSV path for raw inventory snapshots.",
    )
    parser.add_argument(
        "--sku-output",
        type=Path,
        default=Path("etl/sample_data/sku_master.csv"),
        help="Output CSV path for the product reference file used by ETL.",
    )
    parser.add_argument(
        "--product-master-output",
        type=Path,
        default=Path("dbt/seeds/product_master.csv"),
        help="Output CSV path for the dbt product seed.",
    )
    return parser.parse_args()


def build_products(sku_count: int, rng: random.Random) -> list[Product]:
    products: list[Product] = []
    category_names = list(CATEGORY_BLUEPRINTS.keys())
    used_names: set[str] = set()

    for index in range(1, sku_count + 1):
        category = category_names[(index - 1) % len(category_names)]
        blueprint = CATEGORY_BLUEPRINTS[category]
        product_name = blueprint["names"][((index - 1) // len(category_names)) % len(blueprint["names"])]
        if product_name in used_names:
            product_name = f"{product_name} {index:02d}"
        used_names.add(product_name)

        demand_low, demand_high = blueprint["demand"]
        risk_profile = rng.choices(
            population=["stable", "tight", "volatile"],
            weights=[0.50, 0.30, 0.20],
            k=1,
        )[0]

        base_daily_demand = rng.randint(demand_low, demand_high)
        if risk_profile == "tight":
            reorder_cover_days = rng.randint(5, 10)
            target_cover_days = rng.randint(14, 20)
            lead_time_days = rng.randint(4, 8)
            volatility = rng.uniform(0.12, 0.24)
            spike_chance = rng.uniform(0.03, 0.06)
        elif risk_profile == "volatile":
            reorder_cover_days = rng.randint(7, 14)
            target_cover_days = rng.randint(16, 26)
            lead_time_days = rng.randint(3, 7)
            volatility = rng.uniform(0.22, 0.40)
            spike_chance = rng.uniform(0.05, 0.10)
        else:
            reorder_cover_days = rng.randint(9, 18)
            target_cover_days = rng.randint(20, 35)
            lead_time_days = rng.randint(2, 5)
            volatility = rng.uniform(0.08, 0.18)
            spike_chance = rng.uniform(0.01, 0.04)

        products.append(
            Product(
                product_id=f"SKU{index:04d}",
                product_name=product_name,
                category=category,
                base_daily_demand=base_daily_demand,
                volatility=volatility,
                reorder_cover_days=reorder_cover_days,
                target_cover_days=target_cover_days,
                lead_time_days=lead_time_days,
                spike_chance=spike_chance,
            )
        )

    return products


def format_load_date(snapshot_date: date) -> str:
    try:
        return snapshot_date.strftime(DATE_FORMAT)
    except ValueError:
        return f"{snapshot_date.month}/{snapshot_date.day}/{snapshot_date.year}"


def generate_inventory_rows(
    products: list[Product],
    warehouses: list[dict[str, float | str]],
    start_date: date,
    days: int,
    rng: random.Random,
) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []

    for product in products:
        phase = rng.uniform(0.0, math.tau)

        for warehouse in warehouses:
            warehouse_id = str(warehouse["warehouse_id"])
            multiplier = float(warehouse["multiplier"])
            variability = float(warehouse["variability"])
            local_phase = phase + rng.uniform(-0.9, 0.9)
            local_lead_time = max(1, product.lead_time_days + rng.randint(-1, 2))
            reorder_point = max(4, round(product.base_daily_demand * multiplier * product.reorder_cover_days))
            target_stock = max(reorder_point + 8, round(product.base_daily_demand * multiplier * product.target_cover_days))
            on_hand = max(reorder_point + 3, round(target_stock * rng.uniform(0.55, 1.05)))
            inbound_orders: list[tuple[int, int]] = []

            for day_offset in range(days):
                current_date = start_date + timedelta(days=day_offset)
                received_qty = sum(quantity for due_day, quantity in inbound_orders if due_day == day_offset)
                inbound_orders = [(due_day, quantity) for due_day, quantity in inbound_orders if due_day != day_offset]
                available_qty = on_hand + received_qty

                monthly_wave = 1.0 + 0.18 * math.sin((day_offset / 14.0) + local_phase)
                weekly_wave = 0.92 if current_date.weekday() >= 5 else 1.0
                demand_noise = rng.gauss(1.0, product.volatility + variability)
                spike_factor = rng.uniform(1.5, 2.4) if rng.random() < product.spike_chance else 1.0

                units_sold = round(
                    product.base_daily_demand * multiplier * monthly_wave * weekly_wave * demand_noise * spike_factor
                )
                units_sold = max(0, units_sold)
                ending_qty = max(available_qty - units_sold, 0)

                rows.append(
                    {
                        "product_id": product.product_id,
                        "warehouse_id": warehouse_id,
                        "qty_on_hand": ending_qty,
                        "load_dt": format_load_date(current_date),
                        "_sort_date": current_date.isoformat(),
                    }
                )

                if ending_qty <= reorder_point and not inbound_orders:
                    reorder_variation = rng.uniform(0.9, 1.35)
                    order_qty = max(
                        reorder_point,
                        round((target_stock - ending_qty) * reorder_variation),
                    )
                    due_day = min(days + local_lead_time, day_offset + local_lead_time)
                    inbound_orders.append((due_day, order_qty))

                on_hand = ending_qty

    rows.sort(key=lambda row: (str(row["_sort_date"]), str(row["product_id"]), str(row["warehouse_id"])))
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str | int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({fieldname: row[fieldname] for fieldname in fieldnames})


def build_product_rows(products: list[Product]) -> list[dict[str, str]]:
    return [
        {
            "product_id": product.product_id,
            "product_name": product.product_name,
            "category": product.category,
        }
        for product in products
    ]


def main() -> None:
    args = parse_args()
    if not 1 <= args.warehouse_count <= len(WAREHOUSE_PROFILES):
        raise SystemExit(f"--warehouse-count must be between 1 and {len(WAREHOUSE_PROFILES)}")

    rng = random.Random(args.seed)
    products = build_products(args.sku_count, rng)
    warehouses = WAREHOUSE_PROFILES[: args.warehouse_count]
    inventory_rows = generate_inventory_rows(products, warehouses, args.start_date, args.days, rng)
    product_rows = build_product_rows(products)

    write_csv(
        args.inventory_output,
        ["product_id", "warehouse_id", "qty_on_hand", "load_dt"],
        inventory_rows,
    )
    write_csv(args.sku_output, ["product_id", "product_name", "category"], product_rows)
    write_csv(args.product_master_output, ["product_id", "product_name", "category"], product_rows)

    print(
        "Generated "
        f"{len(inventory_rows):,} inventory snapshots for {len(products)} SKUs "
        f"across {len(warehouses)} warehouses and {args.days} days."
    )
    print(f"Inventory output: {args.inventory_output}")
    print(f"SKU reference output: {args.sku_output}")
    print(f"dbt product seed output: {args.product_master_output}")


if __name__ == "__main__":
    main()
