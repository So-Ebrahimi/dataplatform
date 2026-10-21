# Data Platform — Local Setup and Usage Guide

A local data platform using Docker Compose, Apache Spark, Delta Lake, MinIO, Hive Metastore, Trino, ClickHouse, Elasticsearch, and a web application.

## 1. Project Structure

Project root: `C:\Users\404811710\Desktop\dataplatform`

```text
dataplatform/
├── clickhouse/
│   ├── config/
│   │   ├── access_management.xml
│   │   └── storage.xml
│   └── clickhouse-docker-compose.yaml
├── deltalake/
│   ├── data/
│   ├── spark/
│   │   └── ivy/
│   └── deltalake-docker-compose.yaml
├── DockerImages/
├── elastic/
│   └── elastic-docker-compose.yaml
├── trino/
│   └── etc/
│       ├── catalog/
│       └── certs/
└── webapp/
    ├── app/
    │   ├── static/
    │   └── templates/
    ├── demo/
    ├── trino/
    │   └── etc/
    │       └── catalog/
    └── docker-compose.yml
```

The `deltalake/spark/ivy` directory stores Spark's downloaded Maven dependencies. Its contents are generated and can be recreated when necessary.

## 2. Prerequisites

Install and verify:

- Docker Desktop with Docker Compose.
- Python and the `deltalake` and `pyarrow` packages if running the Python example locally.
- Access to the Docker images and any required dependency repositories during initial setup.

Check Docker:

```powershell
docker --version
docker compose version
docker info
```

## 3. Export Docker Images

Save locally available Docker images as TAR archives for backup or offline transfer.

Run from the project root in PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path ".\DockerImages"

docker images --format "{{.Repository}}:{{.Tag}}" |
    Where-Object { $_ -notmatch '^<none>:' } |
    Sort-Object -Unique |
    ForEach-Object {
        $image = $_
        $name = $image -replace '[/ :]', '_'
        docker save -o ".\DockerImages\$name.tar" $image
    }
```

The archives are saved under `DockerImages/`.

Note: This exports images only. It does not back up container data, named volumes, MinIO objects, or configuration files.

## 4. Restore Docker Images

Load the saved images:

```powershell
Get-ChildItem ".\DockerImages\*.tar" |
    ForEach-Object {
        docker load -i $_.FullName
    }
```

Verify:

```powershell
docker images
```

## 5. Create the Docker Network

Create the shared network:

```powershell
docker network create dataplatform
```

If the network already exists, Docker may report an error. Check it with:

```powershell
docker network ls
```

Ensure the Compose services are configured to use the same `dataplatform` network, either as an external network or through a compatible shared network configuration.

## 6. Start the Platform Services

Run the following commands from the project root.

### 6.1 Start Elasticsearch

```powershell
docker compose -f .\elastic\elastic-docker-compose.yaml up -d
```

### 6.2 Start ClickHouse

```powershell
docker compose -f .\clickhouse\clickhouse-docker-compose.yaml up -d
```

### 6.3 Start Delta Lake and Supporting Services

```powershell
docker compose -f .\deltalake\deltalake-docker-compose.yaml up -d
```

This Compose file is expected to define the relevant services, such as Spark, MinIO, and Hive Metastore, according to your configuration.

### 6.4 Start the Web Application

```powershell
docker compose -f .\webapp\docker-compose.yml up -d --build
```

The `-f` option identifies the Compose file explicitly, and `--build` rebuilds images where required.

### 6.5 Verify Running Containers

```powershell
docker ps
```

If a service does not start, inspect its logs:

```powershell
docker compose -f .\deltalake\deltalake-docker-compose.yaml logs --tail 100
```

Use the corresponding Compose file for other services.

## 7. Configure Spark's Ivy Cache

If Spark cannot write to its default Ivy dependency cache, create a writable directory inside the Spark container:

```powershell
docker exec -u 0 spark mkdir -p /tmp/ivy
docker exec -u 0 spark chmod 777 /tmp/ivy
```

The broad permissions are suitable only as a troubleshooting measure in a trusted local development environment. For a persistent or production setup, configure ownership and permissions for the Spark runtime user instead.

## 8. Write and Read Delta Lake Data Using Python

Install the Python dependencies in the environment where the script will run:

```powershell
python -m pip install deltalake pyarrow
```

Create a file named `write_delta.py`:

```python
from deltalake import DeltaTable, write_deltalake
import pyarrow as pa

storage_options = {
    "AWS_ACCESS_KEY_ID": "minioadmin",
    "AWS_SECRET_ACCESS_KEY": "minioadmin123",
    "AWS_ENDPOINT_URL": "http://minio:9000",
    "AWS_REGION": "us-east-1",
    "AWS_ALLOW_HTTP": "true",
}

data = pa.table({
    "id": [1, 2, 3, 4],
    "name": ["Alice", "Bob", "Charlie", "Diana"],
    "age": [25, 30, 35, 28],
})

table_path = "s3://lake/warehouse/people_v2"

write_deltalake(
    table_path,
    data,
    mode="overwrite",
    storage_options=storage_options,
)

dt = DeltaTable(
    table_path,
    storage_options=storage_options,
)

print("Version:", dt.version())
print("Schema:", dt.schema().json())
print("Files:", dt.file_uris())
print(dt.to_pyarrow_table().to_pylist())
```

Run:

```powershell
python .\write_delta.py
```

**Important:** The hostname `minio` must be resolvable from the environment running Python. If Python runs on Windows rather than inside a container on the Docker network, use the published MinIO endpoint, such as `http://localhost:9000`, if that port is mapped by your Compose configuration.

The `overwrite` mode replaces the existing table contents. Use it only when you intend to recreate the example data.

## 9. Open Spark SQL

Launch Spark SQL inside the Spark container with Delta Lake, S3A, and Hive Metastore configuration:

```powershell
docker exec -it spark /opt/spark/bin/spark-sql `
  --packages io.delta:delta-spark_2.13:4.0.1,org.apache.hadoop:hadoop-aws:3.4.1 `
  --conf spark.jars.ivy=/tmp/ivy `
  --conf spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension `
  --conf spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog `
  --conf spark.sql.catalogImplementation=hive `
  --conf spark.hadoop.hive.metastore.uris=thrift://hive-metastore:9083 `
  --conf spark.sql.hive.metastore.version=4.0.1 `
  --conf spark.sql.hive.metastore.jars=maven `
  --conf spark.hadoop.fs.s3a.endpoint=http://minio:9000 `
  --conf spark.hadoop.fs.s3a.access.key=minioadmin `
  --conf spark.hadoop.fs.s3a.secret.key=minioadmin123 `
  --conf spark.hadoop.fs.s3a.path.style.access=true `
  --conf spark.hadoop.fs.s3a.connection.ssl.enabled=false `
  --conf spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem
```

The first startup may download Maven dependencies. This requires network access unless the dependencies are already cached.

If your environment requires a temporary Java home and Ivy configuration, set these variables inside the container before launching Spark:

```text
HOME=/tmp
JAVA_TOOL_OPTIONS=-Duser.home=/tmp -Divy.cache.dir=/tmp/ivy/cache -Divy.home=/tmp/ivy
```

These are environment variables, not SQL statements. Configure them in the container environment or in the shell used to launch Spark.

Verify that the Spark, Delta Lake, Hadoop AWS, and Hive Metastore versions are compatible with one another.

## 10. Create the Hive Database and Delta Tables

Execute the following SQL statements in Spark SQL.

### 10.1 Create the Database

```sql
CREATE DATABASE IF NOT EXISTS lakehouse
LOCATION 's3a://lake/warehouse/catalog/lakehouse.db';
```

Inspect the database:

```sql
DESCRIBE DATABASE EXTENDED lakehouse;
SHOW DATABASES;
```

### 10.2 Register the Delta Tables

Register the existing Delta table created by the Python example:

```sql
CREATE TABLE IF NOT EXISTS lakehouse.people_v2
USING DELTA
LOCATION 's3a://lake/warehouse/people_v2';
```

Register the original `people` table only if a valid Delta table already exists at that location:

```sql
CREATE TABLE IF NOT EXISTS lakehouse.people
USING DELTA
LOCATION 's3a://lake/warehouse/people';
```

A table created with `LOCATION` registers an existing Delta dataset; it does not generate the underlying data by itself.

### 10.3 Inspect Tables and Schema

```sql
SHOW TABLES IN lakehouse;

DESCRIBE lakehouse.people_v2;

DESCRIBE EXTENDED lakehouse.people_v2;
```

### 10.4 Read Data

```sql
SELECT *
FROM lakehouse.people_v2
ORDER BY id;
```

Count records:

```sql
SELECT COUNT(*)
FROM lakehouse.people_v2;
```

Filter and sort records:

```sql
SELECT name, age
FROM lakehouse.people_v2
WHERE age >= 30
ORDER BY age;
```

### 10.5 Insert a New Record

```sql
INSERT INTO lakehouse.people_v2
VALUES (5, 'Eve', 22);
```

Verify the result:

```sql
SELECT *
FROM lakehouse.people_v2
ORDER BY id;
```

The expected example contains five records after the insert, assuming the initial Python write completed successfully and the insert has not already been performed.

## 11. Verify Delta Lake Files in MinIO

Configure the MinIO client alias from inside the MinIO container:

```powershell
docker exec minio mc alias set local http://127.0.0.1:9000 minioadmin minioadmin123
```

List the objects in the original table:

```powershell
docker exec minio mc ls --recursive local/lake/warehouse/people/
```

List the objects in `people_v2`:

```powershell
docker exec minio mc ls --recursive local/lake/warehouse/people_v2/
```

List all objects in the bucket:

```powershell
docker exec minio mc ls --recursive local/lake/
```

A Delta table typically contains a `_delta_log` directory and one or more data files. The exact files and version numbers change as the table is updated.

## 12. Query Delta Lake Through Trino

Connect to the Trino CLI or your configured SQL client.

### 12.1 List Catalogs

```sql
SHOW CATALOGS;
```

### 12.2 Inspect the Delta Catalog

```sql
SHOW SCHEMAS FROM delta;

SHOW TABLES FROM delta.lakehouse;
```

### 12.3 Query the Table

```sql
SELECT *
FROM delta.lakehouse.people_v2
ORDER BY id;
```

Count records:

```sql
SELECT COUNT(*)
FROM delta.lakehouse.people_v2;
```

Filter and sort:

```sql
SELECT name, age
FROM delta.lakehouse.people_v2
WHERE age >= 30
ORDER BY age;
```

The Trino Delta catalog must be configured to access the same object storage and metadata correctly. If the catalog or schema is missing, verify the files under `trino/etc/catalog/` and the corresponding Trino configuration.

## 13. Troubleshooting Checklist

| Problem | What to check |
|---|---|
| Container cannot start | `docker ps -a` and the service logs |
| Docker network already exists | `docker network ls` |
| Spark cannot download dependencies | Maven connectivity, Ivy permissions, and dependency versions |
| MinIO connection fails | Endpoint, port mappings, credentials, and Docker network |
| Delta table cannot be found | Table path and presence of `_delta_log` |
| Hive database or tables are missing | Hive Metastore connectivity and database registration |
| Trino cannot find the Delta table | Delta catalog configuration and object-storage access |
| Python cannot resolve `minio` | Run Python in the Docker network or use a published host endpoint |

## 14. Security Notes

The credentials shown in this README are development examples. Do not use default or hard-coded credentials in production.

For a deployed environment:

- Store secrets in environment variables or a secret manager.
- Restrict MinIO and database network access.
- Avoid exposing internal service ports publicly.
- Back up persistent data and configuration independently of Docker image archives.

