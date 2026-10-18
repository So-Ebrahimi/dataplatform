import os
import re
import sqlparse
from trino.dbapi import connect

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

def connection():
    return connect(
        host=os.getenv("TRINO_HOST", "localhost"),
        port=int(os.getenv("TRINO_PORT", "8080")),
        user=os.getenv("TRINO_USER", "analytics_app"),
        catalog=os.getenv("TRINO_CATALOG", "demo"),
        schema=os.getenv("TRINO_SCHEMA", "public"),
        http_scheme=os.getenv("TRINO_HTTP_SCHEME", "http"),
        # For real deployments configure Trino authentication and HTTPS.
    )

def validate_read_query(sql):
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("Enter a SQL query.")
    if len(sql) > 20000:
        raise ValueError("Query is too long (20,000 character maximum).")
    statements = [s for s in sqlparse.split(sql) if s.strip()]
    if len(statements) != 1:
        raise ValueError("Submit exactly one SQL statement.")
    parsed = sqlparse.parse(statements[0])
    if not parsed:
        raise ValueError("Could not parse SQL.")
    first = parsed[0].token_first(skip_cm=True, skip_ws=True)
    keyword = first.value.upper() if first else ""
    allowed = {"SELECT", "WITH", "SHOW", "DESCRIBE", "DESC", "EXPLAIN"}
    if keyword not in allowed:
        raise ValueError("Only read-only SELECT/WITH/SHOW/DESCRIBE/EXPLAIN queries are allowed.")
    # This is a guardrail, not a complete SQL security boundary.
    # Use a read-only source account, Trino access control, and resource limits.
    return statements[0]

def run_query(sql, max_rows=500):
    sql = validate_read_query(sql)
    conn = connection()
    cur = conn.cursor()
    try:
        cur.execute(sql)
        columns = [
            {"name": c[0], "type": str(c[1]) if len(c) > 1 else ""}
            for c in (cur.description or [])
        ]
        rows = cur.fetchmany(max_rows + 1)
        truncated = len(rows) > max_rows
        rows = rows[:max_rows]
        safe_rows = [[str(v) if v is not None else None for v in row] for row in rows]
        stats = getattr(cur, "stats", {}) or {}
        return {
            "columns": columns,
            "rows": safe_rows,
            "truncated": truncated,
            "query_id": stats.get("queryId"),
            "row_count": len(safe_rows),
        }
    finally:
        cur.close()
        conn.close()

def fetch_all(sql):
    # Metadata queries are static; identifiers are validated before interpolation.
    return run_query(sql, max_rows=1000)
