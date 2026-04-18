# -------
# Reads the Bronze Iceberg table for SkuSense, computes stock-out risk metrics,
# and writes out an Iceberg Silver table.
# Fixed version with proper Iceberg configuration
import sys
import argparse

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
            description="Run the Silver Glue job outside the managed AWS Glue runtime."
        )
        parser.add_argument("--JOB_NAME", default="silver_job_local")
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


# Get job arguments
args = getResolvedOptions(sys.argv, ["JOB_NAME", "BUCKET"])
BUCKET = args["BUCKET"]

if LOCAL_GLUE_RUNTIME:
    print("INFO: awsglue is unavailable; using local stubs. Pass --JOB_NAME/--BUCKET explicitly when running outside AWS Glue.")

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
    
   # 2) Keep Silver as a clean inventory snapshot table.
    silver_df = bronze_df.select(
        "product_id",
        "warehouse_id",
        "load_dt",
        "qty_on_hand"
    )

    
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
  