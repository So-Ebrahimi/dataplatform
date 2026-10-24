
from pyspark.sql import SparkSession
from delta.tables import DeltaTable

spark = (
    SparkSession.builder
    .appName("DeltaLakeMinIO")
    .getOrCreate()
)

table_path = "s3a://lakehouse/events"

# Create sample data
df = spark.createDataFrame(
    [
        (1, "Alice", 100),
        (2, "Bob", 200),
        (3, "Charlie", 300),
    ],
    ["id", "name", "amount"],
)

# Write a Delta table to MinIO
df.write.format("delta").mode("overwrite").save(table_path)

# Read the Delta table
spark.read.format("delta").load(table_path).show()

# Update a row
delta_table = DeltaTable.forPath(spark, table_path)

delta_table.update(
    condition="id = 1",
    set={"amount": "150"},
)

print("After update:")
spark.read.format("delta").load(table_path).show()

# Display transaction history
delta_table.history().show(truncate=False)

spark.stop()
