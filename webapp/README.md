# Trino Self-Service Analytics MVP

A local-development starter using Flask/Jinja, vanilla JavaScript, Trino, and PostgreSQL.

## Features

- Browse Trino catalogs, schemas, tables, and columns
- Preview table rows
- Generate simple aggregate queries with a visual builder
- Run read-only SQL queries and display tabular results
- Save, reopen, and delete named SQL analyses
- Docker Compose development environment with demo sales data

## Requirements

- Docker Desktop or Docker Engine with the Compose plugin
- About 3 GB of available memory for the containers (Trino is the largest component)

## Start

```bash
cp .env.example .env
# Edit .env and replace SECRET_KEY and APP_DB_PASSWORD before use.
docker compose up --build
```

Open:

- Analytics UI: http://localhost:5000
- Trino coordinator UI: http://localhost:8080
- App health check: http://localhost:5000/health

The demo Trino catalog is `demo`, schema is `public`, and the sample table is `sales`.
The source PostgreSQL database is intentionally seeded with synthetic sample data.

To stop:

```bash
docker compose down
```

To remove the app metadata volume too (this permanently deletes saved queries):

```bash
docker compose down -v
```

## Configuration

The web container connects to Trino using service DNS name `trino`, not `localhost`.
The app metadata database is separate from the source database queried through Trino.

- `SECRET_KEY`: Flask session/signing secret
- `APP_DB_PASSWORD`: password for the platform metadata database
- `TRINO_HOST`, `TRINO_PORT`, `TRINO_USER`, `TRINO_CATALOG`, `TRINO_SCHEMA`: Trino connection
- `QUERY_MAX_ROWS`: maximum result rows returned to the browser

The demo connector uses the `dev_source_password` password in `trino/etc/catalog/demo.properties`.
If you change the source database credentials, update both `docker-compose.yml` and that Trino catalog properties file to match.

## Add another data source

Configure a connector in `trino/etc/catalog/` and restart Trino. For example, a catalog properties file named `warehouse.properties` is exposed as the `warehouse` catalog. Follow the official Trino connector documentation for the target system and use secrets rather than committing production credentials.

## Important security limitations

This is a development MVP, not a production-ready multi-user platform.

- There is no login or per-user authorization yet. Do not expose it publicly.
- The SQL validator allows only a limited set of leading SQL keywords and rejects multiple statements, but it is not a security boundary.
- Use a dedicated, least-privilege, SELECT-only account for every data source and configure Trino access control, authentication, TLS, and resource groups.
- Do not expose the unauthenticated Trino coordinator to untrusted networks.
- Add request authentication, CSRF protections for cookie-authenticated flows, rate limits, query timeouts/cancellation, audit logging, and per-user saved-query ownership before production.
- Query results are serialized to strings for JSON compatibility; add typed serialization/pagination if needed.
- Docker image versions should be reviewed and pinned according to your organization's patching policy.

## Troubleshooting

- **UI says catalog unavailable:** wait for Trino to start, then inspect `docker compose logs trino web`.
- **Connection refused:** run `docker compose ps` and confirm all services are running.
- **No tables:** check `docker compose logs source-db`; its initialization script runs only when its data volume is first created.
- **Changed seed SQL but data didn't change:** `docker compose down -v` resets the demo data and app metadata volumes; this deletes saved analyses.
- **Query rejected:** the MVP only permits a single read-oriented query beginning with `SELECT`, `WITH`, `SHOW`, `DESCRIBE`, `DESC`, or `EXPLAIN`.

## Project layout

```text
app/
  __init__.py       Flask app factory and extension setup
  models.py         Saved query model
  routes.py         Catalog, preview, query, and saved-query API
  trino_service.py  Trino connection and query guardrails
  templates/
    index.html      Main application shell
  static/
    app.js          Browser interactions and API calls
    style.css       Responsive UI
demo/init.sql       Synthetic sample sales table
trino/etc/          Trino coordinator and demo connector configuration
docker-compose.yml  Local multi-container environment
```
