
from pyspark.sql import SparkSession
from delta import configure_spark_with_delta_pip
from delta.tables import DeltaTable

spark = (
    configure_spark_with_delta_pip(
        SparkSession.builder
        .appName("WriteDeltaPeople")
        .master("spark://spark-master:7077")
        .config(
            "spark.sql.extensions",
            "io.delta.sql.DeltaSparkSessionExtension",
        )
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9100")
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin")
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123")
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl",
                "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
        .config("spark.sql.shuffle.partitions", "2")
    )
    .getOrCreate()
)

try:
    table_path = "s3a://lake/warehouse/people"

    data = [
        (1, "Alice", 25),
        (2, "Bob", 30),
        (3, "Charlie", 35),
        (4, "Diana", 28),
    ]

    columns = ["id", "name", "age"]

    df = spark.createDataFrame(data, columns)

    # Write the Delta table
    (
        df.write
        .format("delta")
        .mode("overwrite")
        .save(table_path)
    )

    # Read it back
    dt = DeltaTable.forPath(spark, table_path)

    print("Version:", dt.history(1).select("version").first()["version"])
    print("Schema:", spark.read.format("delta").load(table_path).schema.json())

    print("Files:")
    for file in dt.toDF().inputFiles():
        print(file)

    print("Rows:")
    spark.read.format("delta").load(table_path).show(truncate=False)

finally:
    spark.stop()
