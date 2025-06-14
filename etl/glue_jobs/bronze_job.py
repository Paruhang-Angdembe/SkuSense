import os 
from awsglue.context import GlueContext
from pyspark.context import SparkContext
from pyspark.sql.functions import col, row_number, desc
from pyspark.sql.window import Window

# Glue/Spark session bootstrap
sc = SparkContext()
glue = GlueContext(sc)
spark = glue.spark_session

# Configurables - keep these small & obvious for now.
DATABASE = "skusense_raw_db" # Glue databse created by crawler
RAW_TABLE = "inventory_levels" # Raw table name
BUCKET = os.environ.get("BUCKET")
OUTPUT_PATH = f"s3://{BUCKET}/bronze/"

# Read raw table
df = spark.table(f"{DATABASE}.{RAW_TABLE}")

# Deduplicate: pick highest qty_on_hand per (product_id, load_dt)
window = Window.partitionBy("product_id", "load_dt").orderBy(desc("qty_on_hand"))
df_dedup = (df
            .withColumn("rn", row_number().over(window))
            .filter(col("rn") == 1)
            .drop("rn")
)

# Write Iceberg table
(df_dedup
 .write
 .format("iceberg")
 .mode("overwrite")
 .option("write-format", "parquet")
 .option("partitioning", "product_id,load_dt")
 .save(OUTPUT_PATH)
)

print("Bronze Iceberg write complete.")