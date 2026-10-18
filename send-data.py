
import json
import requests
import clickhouse_connect
import trino

from requests.auth import HTTPBasicAuth

# ============================================================
# CONFIGURATION
# ============================================================

# Elasticsearch: HTTPS + Basic Auth
ES_URL = "https://localhost:9200"
ES_USER = "elastic"
ES_PASSWORD = "12345678"

# Preferred: path to Elasticsearch CA certificate.
# Example: "/etc/elasticsearch/certs/http_ca.crt"
ES_CA_CERT = "/path/to/http_ca.crt"

# Set to True ONLY for local testing without a CA certificate.
ES_VERIFY_SSL = False

# ClickHouse
CH_HOST = "localhost"
CH_PORT = 8123
CH_USER = "default"
CH_PASSWORD = "password"
CH_DATABASE = "default"

# Trino
TRINO_HOST = "localhost"
TRINO_PORT = 8080
TRINO_USER = "test"

# ============================================================
# ELASTICSEARCH CONNECTION
# ============================================================

es = requests.Session()
es.auth = HTTPBasicAuth(ES_USER, ES_PASSWORD)
es.headers.update({"Content-Type": "application/json"})
es.verify = ES_CA_CERT if ES_VERIFY_SSL else False

if not ES_VERIFY_SSL:
    import urllib3
    urllib3.disable_warnings(
        urllib3.exceptions.InsecureRequestWarning
    )


def check_response(response):
    """Raise an informative error for unsuccessful HTTP requests."""
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(
            f"Elasticsearch request failed: "
            f"{response.status_code} {response.text}"
        ) from exc


def setup_elasticsearch():
    print("\n=== Elasticsearch ===")

    response = es.get(ES_URL, timeout=15)
    check_response(response)
    print("Connected:", response.json().get("cluster_name"))

    # For a repeatable test, recreate only this dedicated test index.
    response = es.delete(f"{ES_URL}/orders")
    if response.status_code not in (200, 404):
        check_response(response)

    # Create index and explicit field mappings
    response = es.put(
        f"{ES_URL}/orders",
        json={
            "mappings": {
                "properties": {
                    "order_id": {"type": "integer"},
                    "customer_id": {"type": "integer"},
                    "product": {"type": "keyword"},
                    "amount": {"type": "double"},
                    "status": {"type": "keyword"},
                }
            }
        },
        timeout=15,
    )
    check_response(response)

    orders = [
        {
            "order_id": 1,
            "customer_id": 101,
            "product": "Laptop",
            "amount": 1200.50,
            "status": "PAID",
        },
        {
            "order_id": 2,
            "customer_id": 102,
            "product": "Phone",
            "amount": 799.99,
            "status": "PAID",
        },
        {
            "order_id": 3,
            "customer_id": 101,
            "product": "Mouse",
            "amount": 25.50,
            "status": "PENDING",
        },
        {
            "order_id": 4,
            "customer_id": 103,
            "product": "Keyboard",
            "amount": 75.00,
            "status": "PAID",
        },
    ]

    # Bulk insert
    bulk_data = "".join(
        json.dumps(
            {"index": {"_index": "orders", "_id": str(order["order_id"])}}
        )
        + "\n"
        + json.dumps(order)
        + "\n"
        for order in orders
    )

    response = es.post(
        f"{ES_URL}/_bulk",
        data=bulk_data,
        headers={"Content-Type": "application/x-ndjson"},
        timeout=30,
    )
    check_response(response)

    bulk_result = response.json()
    if bulk_result.get("errors"):
        errors = [
            item for item in bulk_result["items"]
            if any(action.get("error") for action in item.values())
        ]
        raise RuntimeError(f"Bulk insert errors: {errors}")

    check_response(es.post(f"{ES_URL}/orders/_refresh", timeout=15))

    count = es.get(f"{ES_URL}/orders/_count", timeout=15).json()["count"]
    print(f"Inserted {count} Elasticsearch documents")


# ============================================================
# CLICKHOUSE CONNECTION AND DATA
# ============================================================

def setup_clickhouse():
    print("\n=== ClickHouse ===")

    client = clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD,
        connect_timeout=15,
    )

    client.command(f"CREATE DATABASE IF NOT EXISTS {CH_DATABASE}")

    client.command(f"""
        CREATE TABLE IF NOT EXISTS {CH_DATABASE}.order_items
        (
            order_id UInt32,
            customer_id UInt32,
            product String,
            quantity UInt32,
            unit_price Float64
        )
        ENGINE = MergeTree
        ORDER BY order_id
    """)

    items = [
        (1, 101, "Laptop", 1, 1200.50),
        (2, 102, "Phone", 1, 799.99),
        (3, 101, "Mouse", 2, 25.50),
        (4, 103, "Keyboard", 1, 75.00),
        (5, 104, "Monitor", 2, 300.00),
    ]

    # This script is for a dedicated test table.
    client.command(f"TRUNCATE TABLE {CH_DATABASE}.order_items")

    client.insert(
        f"{CH_DATABASE}.order_items",
        items,
        column_names=[
            "order_id",
            "customer_id",
            "product",
            "quantity",
            "unit_price",
        ],
    )

    result = client.query(
        f"SELECT count() FROM {CH_DATABASE}.order_items"
    )
    print(f"Inserted {result.result_rows[0][0]} ClickHouse rows")

    client.close()


# ============================================================
# TRINO CONNECTION AND QUERIES
# ============================================================

def test_trino():
    print("\n=== Trino ===")

    conn = trino.dbapi.connect(
        host=TRINO_HOST,
        port=TRINO_PORT,
        user=TRINO_USER,
        catalog="clickhouse",
        schema="demo",
    )

    cursor = conn.cursor()

    queries = {
        "ClickHouse": """
            SELECT order_id, product, quantity, unit_price
            FROM clickhouse.default.order_items
            ORDER BY order_id
        """,
        "Cross-database JOIN": """
            SELECT
                e.order_id,
                e.product,
                e.status,
                c.quantity,
                c.unit_price,
                c.quantity * c.unit_price AS line_total
            FROM elasticsearch.default.orders e
            JOIN clickhouse.default.order_items c
                ON e.order_id = c.order_id
            ORDER BY e.order_id
        """,
    }

    try:
        for name, sql in queries.items():
            print(f"\n--- {name} ---")
            cursor.execute(sql)

            columns = [column[0] for column in cursor.description]
            print(" | ".join(columns))

            for row in cursor.fetchall():
                print(" | ".join(str(value) for value in row))
    finally:
        cursor.close()
        conn.close()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    setup_elasticsearch()
    setup_clickhouse()
    # test_trino()
    print("\nAll tests completed successfully.")
