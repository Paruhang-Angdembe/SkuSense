# etl/glue_jobs/bronze_job.py
# -------
# Creates/Updates the Bronze Iceberg table for SkuSense
# if the table doesn't exist yet, .mode("append") make Spark
# Create it automatically; future runs can switch to "overwrite"

import argparse
import sys

try:
    from awsglue.context import GlueContext
    from awsglue.utils import getResolvedOptions
    from awsglue.job import Job
    LOCAL_GLUE_RUNTIME = False
except ModuleNotFoundError as exc:
    if exc.name != "awsglue":
        raise

    LOCAL_GLUE_RUNTIME = True

    class GlueContext:
        def __init__(self, spark_context):
            self.spark_context = spark_context

    class Job:
        def __init__(self, glue_context):
            self.glue_context = glue_context

        def init(self, *_args, **_kwargs):
            return None

        def commit(self):
            return None

    def getResolvedOptions(argv, options):
        parser = argparse.ArgumentParser(
            description="Run the Bronze Glue job outside the managed AWS Glue runtime."
        )
        parser.add_argument("--JOB_NAME", default="bronze_job_local")
        parser.add_argument("--BUCKET")
        known_args, _ = parser.parse_known_args(argv[1:])
        values = vars(known_args)
        missing = [name for name in options if not values.get(name)]
        if missing:
            parser.error(f"missing required arguments: {', '.join(f'--{name}' for name in missing)}")
        return {name: values[name] for name in options}

try:
    from pyspark.sql import SparkSession
except ModuleNotFoundError as exc:
    if exc.name != "pyspark":
        raise
    raise SystemExit(
        "pyspark is not installed in this environment. "
        "Run this job in the AWS Glue Docker image or install a compatible Spark runtime first."
    ) from exc

from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Get job arguments
args = getResolvedOptions(sys.argv, ["JOB_NAME", "BUCKET"])
BUCKET = args["BUCKET"]

if LOCAL_GLUE_RUNTIME:
    print("INFO: awsglue is unavailable; using local stubs. Pass --JOB_NAME/--BUCKET explicitly when running outside AWS Glue.")

# CRITICAL: Configure Spark with Iceberg extensions (same as Silver job)
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

# Parameters & Constants
RAW_DB = "skusense_raw_db"
RAW_TABLE = "inventory_levels_csv"
BRONZE_DB = "skusense_bronze_db"
BRONZE_TABLE = "inventory_bronze"
OUTPUT_PATH = f"s3://{BUCKET}/bronze/"

try:
    print(f"DEBUG: reading raw → {RAW_DB}.{RAW_TABLE}")
    df_raw = spark.table(f"{RAW_DB}.{RAW_TABLE}")
    print(f"Raw record count: {df_raw.count()}")
    
    # Deduplicate per (product_id, warehouse_id, load_dt)
    w = Window.partitionBy("product_id", "warehouse_id", "load_dt").orderBy(F.desc("qty_on_hand"))
    df_dedup = (
        df_raw
        .withColumn("rn", F.row_number().over(w))
        .filter(F.col("rn") == 1)
        .drop("rn")
    )
    
    print(f"After dedup record count: {df_dedup.count()}")
    
    # Ensure Bronze DB exists using catalog prefix
    spark.sql(f"CREATE DATABASE IF NOT EXISTS glue_catalog.{BRONZE_DB}")
    
    # Write to Iceberg table
     # Write to Iceberg table using catalog prefix (consistent with Silver job)
    print(f"Writing to Iceberg table: glue_catalog.{BRONZE_DB}.{BRONZE_TABLE}")
    (df_dedup
        .write
        .format("iceberg")
        .mode("overwrite")
        .option("write-format", "parquet")
        .option("path", OUTPUT_PATH)
        .saveAsTable(f"glue_catalog.{BRONZE_DB}.{BRONZE_TABLE}")
    )
    
    print("✅ Bronze Iceberg write complete.")
    
except Exception as e:
    print(f"ERROR: {str(e)}")
    print("Full error details:")
    import traceback
    traceback.print_exc()
    raise e
finally:
    job.commit()
