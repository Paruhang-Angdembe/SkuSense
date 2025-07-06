# -------
# Reads the Bronze Iceberg table for SkuSense, computes stock-out risk metrics,
# and writes out an Iceberg Silver table.
# Fixed version with proper Iceberg configuration
import sys
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.window import Window

# Get job arguments - handle optional BUCKET parameter
try:
    args = getResolvedOptions(sys.argv, ["JOB_NAME", "BUCKET"])
    BUCKET = args["BUCKET"]
except Exception:
    # Fallback: try to get from optional args or use default
    args = getResolvedOptions(sys.argv, ["JOB_NAME"])
    # Replace 'your-default-bucket-name' with your actual bucket name
    BUCKET = "your-default-bucket-name"
    print(f"Using default bucket: {BUCKET}")

# CRITICAL: Configure Spark with Iceberg extensions (same as Bronze job)
spark = SparkSession.builder \
    .appName(args['JOB_NAME']) \
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
    .config("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.glue_catalog.warehouse", f"s3://{BUCKET}/warehouse/") \
    .config("spark.sql.catalog.glue_catalog.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog") \
    .config("spark.sql.catalog.glue_catalog.io-impl", "org.apache.iceberg.aws.s3.S3FileIO") \
    .getOrCreate()

# Initialize Glue context
sc = spark.sparkContext
glue = GlueContext(sc)
job = Job(glue)
job.init(args['JOB_NAME'], args)

# ─── Constants ─────────────────────────────────────────────────────────────────
BRONZE_DB = "skusense_bronze_db"
BRONZE_TABLE = "inventory_bronze"
SILVER_DB = "skusense_silver_db"
SILVER_TABLE = "inventory_silver"
OUTPUT_PATH = f"s3://{BUCKET}/silver/"

try:
    # 1) Read Bronze Iceberg table using catalog prefix
    print(f"DEBUG: reading Bronze → glue_catalog.{BRONZE_DB}.{BRONZE_TABLE}")
    bronze_df = spark.table(f"glue_catalog.{BRONZE_DB}.{BRONZE_TABLE}")
    print(f"DEBUG: Bronze record count = {bronze_df.count()}")
    
    # 2) Compute metrics
    # Example: turnover_ratio = qty_on_hand / (some business-logic window)
    # days_until_stockout = qty_on_hand / avg_daily_usage
    # Here we approximate avg_daily_usage via a 7-day window:
    window7 = Window.partitionBy("product_id").orderBy("load_dt").rowsBetween(-6, 0)
    
    with_usage = bronze_df.withColumn("avg_daily_usage",
        F.round(F.avg("qty_on_hand").over(window7), 2))
    
    silver_df = with_usage \
        .withColumn("days_until_stockout",
            F.when(F.col("avg_daily_usage") > 0,
                F.round(F.col("qty_on_hand") / F.col("avg_daily_usage"), 2))
            .otherwise(F.lit(None))) \
        .withColumn("turnover_ratio",
            F.when(F.col("days_until_stockout") > 0,
                F.round(F.col("qty_on_hand") / F.col("days_until_stockout"), 2))
            .otherwise(F.lit(None))) \
        .withColumn("stock_status",
            F.when(F.col("days_until_stockout") <= 7, "CRITICAL")
            .when(F.col("days_until_stockout") <= 14, "LOW")
            .when(F.col("days_until_stockout") <= 30, "MEDIUM")
            .otherwise("HEALTHY")) \
        .withColumn("reorder_flag",
            F.when(F.col("days_until_stockout") <= 14, True)
            .otherwise(False))
    
    print(f"DEBUG: After metrics count = {silver_df.count()}")
    
    # 3) Ensure Silver DB exists
    spark.sql(f"CREATE DATABASE IF NOT EXISTS glue_catalog.{SILVER_DB}")
    
    # 4) Write Iceberg Silver table using catalog prefix
    print(f"Writing Silver Iceberg → glue_catalog.{SILVER_DB}.{SILVER_TABLE}")
    (silver_df
        .write
        .format("iceberg")
        .mode("overwrite")
        .option("write-format", "parquet")
        .option("path", OUTPUT_PATH)
        .saveAsTable(f"glue_catalog.{SILVER_DB}.{SILVER_TABLE}")
    )
    
    print("✅ Silver Iceberg write complete.")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    raise e
finally:
    job.commit()