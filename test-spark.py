from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("ClusterCompatibilityTest")
    .master("spark://localhost:7077")
    .config("spark.driver.host", "host.docker.internal")
    .config("spark.driver.bindAddress", "0.0.0.0")
    .config("spark.driver.port", "39000")
    .config("spark.driver.blockManager.port", "39001")
    .config("spark.cores.max", "2")
    .getOrCreate()
)

spark.range(10).show()
spark.stop()