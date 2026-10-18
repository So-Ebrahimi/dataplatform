from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select
from app import db
from app.models import SavedQuery
from app.trino_service import run_query, fetch_all, IDENTIFIER

api = Blueprint("api", __name__)

def error(message, status=400):
    return jsonify({"error": message}), status

@api.get("/catalogs")
def catalogs():
    try:
        result = fetch_all("SHOW CATALOGS")
        return jsonify({"catalogs": [r[0] for r in result["rows"]]})
    except Exception as exc:
        current_app.logger.exception("Catalog lookup failed")
        return error("Could not load Trino catalogs. Check the Trino connection.", 502)

@api.get("/schemas")
def schemas():
    catalog = request.args.get("catalog", "")
    if not IDENTIFIER.fullmatch(catalog):
        return error("Invalid catalog identifier.")
    try:
        result = fetch_all(f"SHOW SCHEMAS FROM {catalog}")
        return jsonify({"schemas": [r[0] for r in result["rows"]]})
    except Exception:
        current_app.logger.exception("Schema lookup failed")
        return error("Could not load schemas.", 502)

@api.get("/tables")
def tables():
    catalog = request.args.get("catalog", "")
    schema = request.args.get("schema", "")
    if not IDENTIFIER.fullmatch(catalog) or not IDENTIFIER.fullmatch(schema):
        return error("Invalid catalog or schema identifier.")
    try:
        result = fetch_all(f"SHOW TABLES FROM {catalog}.{schema}")
        return jsonify({"tables": [r[0] for r in result["rows"]]})
    except Exception:
        current_app.logger.exception("Table lookup failed")
        return error("Could not load tables.", 502)

@api.get("/columns")
def columns():
    catalog, schema, table = (
        request.args.get("catalog", ""),
        request.args.get("schema", ""),
        request.args.get("table", ""),
    )
    if not all(IDENTIFIER.fullmatch(v) for v in (catalog, schema, table)):
        return error("Invalid catalog, schema, or table identifier.")
    try:
        result = fetch_all(f"DESCRIBE {catalog}.{schema}.{table}")
        return jsonify({"columns": [
            {"name": r[0], "type": r[1], "extra": r[2] if len(r) > 2 else ""}
            for r in result["rows"]
        ]})
    except Exception:
        current_app.logger.exception("Column lookup failed")
        return error("Could not load table columns.", 502)

@api.post("/preview")
def preview():
    data = request.get_json(silent=True) or {}
    catalog, schema, table = data.get("catalog", ""), data.get("schema", ""), data.get("table", "")
    if not all(isinstance(v, str) and IDENTIFIER.fullmatch(v) for v in (catalog, schema, table)):
        return error("Invalid catalog, schema, or table identifier.")
    try:
        result = run_query(
            f"SELECT * FROM {catalog}.{schema}.{table} LIMIT 100",
            max_rows=100,
        )
        return jsonify(result)
    except Exception:
        current_app.logger.exception("Table preview failed")
        return error("Could not preview this table.", 502)

@api.post("/query")
def query():
    data = request.get_json(silent=True) or {}
    try:
        result = run_query(data.get("sql", ""), current_app.config["QUERY_MAX_ROWS"])
        return jsonify(result)
    except ValueError as exc:
        return error(str(exc), 400)
    except Exception:
        current_app.logger.exception("Query execution failed")
        return error("Query failed. Check SQL syntax, permissions, and Trino logs.", 502)

@api.get("/saved-queries")
def list_saved_queries():
    items = db.session.execute(
        select(SavedQuery).order_by(SavedQuery.created_at.desc())
    ).scalars().all()
    return jsonify({"queries": [
        {"id": q.id, "name": q.name, "sql": q.sql,
         "created_at": q.created_at.isoformat() if q.created_at else None}
        for q in items
    ]})

@api.post("/saved-queries")
def save_query():
    data = request.get_json(silent=True) or {}
    name, sql = data.get("name", ""), data.get("sql", "")
    if not isinstance(name, str) or not name.strip() or len(name) > 160:
        return error("Name is required and must be 160 characters or fewer.")
    try:
        from app.trino_service import validate_read_query
        sql = validate_read_query(sql)
    except ValueError as exc:
        return error(str(exc))
    item = SavedQuery(name=name.strip(), sql=sql)
    db.session.add(item)
    db.session.commit()
    return jsonify({"id": item.id, "name": item.name, "sql": item.sql}), 201

@api.delete("/saved-queries/<int:query_id>")
def delete_saved_query(query_id):
    item = db.session.get(SavedQuery, query_id)
    if not item:
        return error("Saved query not found.", 404)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"deleted": True})
