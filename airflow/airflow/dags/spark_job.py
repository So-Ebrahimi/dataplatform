
from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("AirflowSparkExample")
    .getOrCreate()
)

try:
    result = spark.range(1, 100001).count()
    print(f"Spark job completed successfully. Count: {result}")
finally:
    spark.stop()
