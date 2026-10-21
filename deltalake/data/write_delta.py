from deltalake import write_deltalake, DeltaTable
import pyarrow as pa

table_uri = "s3://lake/warehouse/people"

storage_options = {
    "AWS_ACCESS_KEY_ID": "minioadmin",
    "AWS_SECRET_ACCESS_KEY": "minioadmin123",
    "AWS_ENDPOINT_URL": "http://minio:9000",
    "AWS_REGION": "us-east-1",
    "AWS_ALLOW_HTTP": "true",
}

# Create data using PyArrow
data = pa.table({
    "id": [1, 2, 3],
    "name": ["Alice", "Bob", "Charlie"],
    "age": [25, 30, 35],
})

# Write a Delta Lake table to MinIO
write_deltalake(
    table_uri,
    data,
    mode="overwrite",
    storage_options=storage_options,
)

print("Delta table created successfully!")

# Read the table back
table = DeltaTable(
    table_uri,
    storage_options=storage_options,
)

print(table.to_pyarrow_table().to_pydict())