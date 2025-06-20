# etl/glue_jobs/bronze_job.py
# -------
# Creates/Updates the Bronze Iceberg table for SkuSense
# if the table doesn't exist yet, .mode("append") make Spark
# Create it automatically; future runs can switch to "overwrite"

import sys
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Initialize Glue/Spark session with Iceberg Configuration
sc = SparkContext()
glue = GlueContext(sc)
spark = glue.spark_session

args = getResolvedOptions(sys.argv, ["JOB_NAME", "BUCKET"])
job = Job(glue)
job.init(args['JOB_NAME'], args)

# Parameters & Constant
BUCKET = args["BUCKET"]
RAW_DB = "skusense_raw_db"
RAW_TABLE = "inventory_levels_csv"
BRONZE_DB = "skusense_bronze_db"
BRONZE_TB = "inventory_bronze"
OUTPUT_PATH = f"s3://{BUCKET}/bronze/"

try:
    print("Debug - reading", f"{RAW_DB}.{RAW_TABLE}")
    df_raw = spark.table(f"{RAW_DB}.{RAW_TABLE}")
    
    print(f"Raw record count: {df_raw.count()}")
    
    # Deduplicate per (product_id, load_dt)
    w = Window.partitionBy("product_id", "load_dt").orderBy(F.desc("qty_on_hand"))
    df_dedup = (df_raw
        .withColumn("rn", F.row_number().over(w))
        .filter(F.col("rn") == 1)
        .drop("rn")
    )
    
    print(f"After dedup record count: {df_dedup.count()}")
    
    # Register DB (idempotent)
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {BRONZE_DB}")
    
    # Write to Iceberg table
    print(f"Writing to Iceberg table: {BRONZE_DB}.{BRONZE_TB}")
    (df_dedup
        .write
        .format("iceberg")
        .mode("overwrite")
        .option("write-format", "parquet")
        .option("path", OUTPUT_PATH)
        .saveAsTable(f"{BRONZE_DB}.{BRONZE_TB}")
    )
    
    print("Bronze Iceberg write complete.")
    
except Exception as e:
    print(f"ERROR: {str(e)}")
    print("Full error details:")
    import traceback
    traceback.print_exc()
    raise e
finally:
    job.commit()