from deltalake import DeltaTable, write_deltalake
import pyarrow as pa

storage_options = {
    "AWS_ACCESS_KEY_ID": "minioadmin",
    "AWS_SECRET_ACCESS_KEY": "minioadmin123",
    "AWS_ENDPOINT_URL": "http://127.0.0.1:9100",
    "AWS_REGION": "us-east-1",
    "AWS_ALLOW_HTTP": "true",
}

data = pa.table({
    "id": [1, 2, 3, 4],
    "name": ["Alice", "Bob", "Charlie", "Diana"],
    "age": [25, 30, 35, 28],
})

table_path = "s3://lake/warehouse/people"

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