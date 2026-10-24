import os
import socket
import time

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

NUM_ROWS = int(os.getenv("NUM_ROWS", "10000000"))
NUM_DAYS = 30
NUM_WRITE_PARTITIONS = int(os.getenv("NUM_WRITE_PARTITIONS", "16"))

# The host runs this Python driver, and Spark executors run in
# Docker containers. This endpoint must be reachable by BOTH.
MINIO_ENDPOINT = os.getenv(
    "MINIO_ENDPOINT",
    "http://host.docker.internal:9100",
)

MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin123"

BUCKET = os.getenv("MINIO_BUCKET", "spark-delta")
TABLE_PATH = f"s3a://{BUCKET}/large-events/"


# ------------------------------------------------------------
# Spark session
# ------------------------------------------------------------

spark = (
    SparkSession.builder
    .appName("LargeMinIODeltaLakeTest")
    .master("spark://localhost:7077")

    # Remote driver connectivity: retain your working settings.
    .config("spark.driver.host", "host.docker.internal")
    .config("spark.driver.bindAddress", "0.0.0.0")
    .config("spark.driver.port", "39000")
    .config("spark.driver.blockManager.port", "39001")

    # Delta Lake support.
    .config(
        "spark.jars.packages",
        ",".join([
            "io.delta:delta-spark_2.13:4.0.1",
            "org.apache.hadoop:hadoop-aws:3.4.1",
        ]),
    )
    .config(
        "spark.sql.extensions",
        "io.delta.sql.DeltaSparkSessionExtension",
    )
    .config(
        "spark.sql.catalog.spark_catalog",
        "org.apache.spark.sql.delta.catalog.DeltaCatalog",
    )

    # MinIO / S3A configuration.
    .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
    .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
    .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
    .config("spark.hadoop.fs.s3a.endpoint.region", "us-east-1")
    .config(
        "spark.hadoop.fs.s3a.impl",
        "org.apache.hadoop.fs.s3a.S3AFileSystem",
    )

    # Large-write test tuning.
    .config("spark.cores.max", "8")
    .config("spark.executor.cores", "2")
    .config("spark.sql.shuffle.partitions", str(NUM_WRITE_PARTITIONS))
    .config("spark.sql.files.maxRecordsPerFile", "1000000")
    .config("spark.sql.parquet.compression.codec", "snappy")

    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")


try:
    sc = spark.sparkContext

    print("=" * 70)
    print("SPARK / MINIO / DELTA LAKE LOAD TEST")
    print("=" * 70)
    print("Spark version:", spark.version)
    print("Master:", sc.master)
    print("Application ID:", sc.applicationId)
    print("Driver hostname:", socket.gethostname())
    print("Rows to generate:", f"{NUM_ROWS:,}")
    print("Output:", TABLE_PATH)

    # --------------------------------------------------------
    # 1. Generate synthetic data in a distributed fashion
    # --------------------------------------------------------

    print("\nGenerating synthetic data...")

    start = time.time()

    df = (
        spark.range(0, NUM_ROWS, 1, numPartitions=NUM_WRITE_PARTITIONS)
        .withColumnRenamed("id", "event_id")
        .withColumn(
            "customer_id",
            (F.col("event_id") % 1_000_000).cast("long"),
        )
        .withColumn(
            "amount",
            F.round(
                (
                    (F.col("event_id") % 100_000) * F.lit(0.13)
                    + F.lit(10.0)
                ),
                2,
            ),
        )
        .withColumn(
            "quantity",
            (F.col("event_id") % 10 + 1).cast("int"),
        )
        .withColumn(
            "status",
            F.when(F.col("event_id") % 10 == 0, "CANCELLED")
            .when(F.col("event_id") % 5 == 0, "PENDING")
            .otherwise("COMPLETED"),
        )
        .withColumn(
            "event_date",
            F.date_add(
                F.to_date(F.lit("2026-01-01")),
                (F.col("event_id") % NUM_DAYS).cast("int"),
            ),
        )
        .withColumn(
            "description",
            F.concat(
                F.lit("Synthetic transaction number "),
                F.col("event_id").cast("string"),
                F.lit(" for customer "),
                F.col("customer_id").cast("string"),
            ),
        )
        .withColumn(
            "payload",
            F.to_json(
                F.struct(
                    F.col("event_id"),
                    F.col("customer_id"),
                    F.col("amount"),
                    F.col("quantity"),
                    F.col("status"),
                )
            ),
        )
    )

    df.printSchema()

    # --------------------------------------------------------
    # 2. Write Delta Lake table to MinIO
    # --------------------------------------------------------

    print("\nWriting Delta table to MinIO...")
    print("This is the main load test; duration depends on hardware.")

    write_start = time.time()

    (
        df.repartition(NUM_WRITE_PARTITIONS, "event_date")
        .write
        .format("delta")
        .mode("overwrite")
        .partitionBy("event_date")
        .option("compression", "snappy")
        .save(TABLE_PATH)
    )

    write_seconds = time.time() - write_start

    print(f"Write completed in {write_seconds:.2f} seconds")
    print(f"Write throughput: {NUM_ROWS / max(write_seconds, 0.001):,.0f} rows/sec")

    # --------------------------------------------------------
    # 3. Read the table back from MinIO
    # --------------------------------------------------------

    print("\nReading Delta table from MinIO...")

    read_start = time.time()

    delta_df = spark.read.format("delta").load(TABLE_PATH)

    # Full scan: force Spark to process all the rows.
    stats = (
        delta_df
        .agg(
            F.count("*").alias("row_count"),
            F.sum("amount").alias("total_amount"),
            F.min("event_id").alias("min_event_id"),
            F.max("event_id").alias("max_event_id"),
            F.countDistinct("customer_id").alias("distinct_customers"),
        )
        .first()
    )

    read_seconds = time.time() - read_start

    print(f"Read and aggregation completed in {read_seconds:.2f} seconds")
    print("Rows:", f"{stats['row_count']:,}")
    print("Total amount:", stats["total_amount"])
    print("Min event ID:", stats["min_event_id"])
    print("Max event ID:", stats["max_event_id"])
    print("Distinct customers:", stats["distinct_customers"])

    # --------------------------------------------------------
    # 4. Validate the test
    # --------------------------------------------------------

    assert stats["row_count"] == NUM_ROWS, (
        f"Row count mismatch: expected {NUM_ROWS}, "
        f"got {stats['row_count']}"
    )

    assert stats["min_event_id"] == 0
    assert stats["max_event_id"] == NUM_ROWS - 1

    print("\nSample rows:")
    delta_df.orderBy("event_id").show(10, truncate=False)

    print("\nRows by status:")
    (
        delta_df.groupBy("status")
        .count()
        .orderBy("status")
        .show()
    )

    # --------------------------------------------------------
    # 5. Inspect Delta transaction history
    # --------------------------------------------------------

    from delta.tables import DeltaTable

    print("\nDelta Lake history:")
    (
        DeltaTable.forPath(spark, TABLE_PATH)
        .history(5)
        .select("version", "timestamp", "operation", "operationMetrics")
        .show(truncate=False)
    )

    print("=" * 70)
    print("TEST PASSED")
    print("Delta table:", TABLE_PATH)
    print(f"Rows written and validated: {stats['row_count']:,}")
    print(f"Write duration: {write_seconds:.2f} seconds")
    print(f"Read + aggregation duration: {read_seconds:.2f} seconds")
    print("=" * 70)

finally:
    spark.stop()