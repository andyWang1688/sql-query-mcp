# sql-query-mcp

[中文版](README-zh.md)

A general-purpose MCP server that lets AI work with multiple databases within
clear boundaries.

[![sql-query-mcp MCP server](https://glama.ai/mcp/servers/andyWang1688/sql-query-mcp/badges/card.svg)](https://glama.ai/mcp/servers/andyWang1688/sql-query-mcp)

## Current database support

| Database | Status | Current availability |
| --- | --- | --- |
| PostgreSQL | Supported | Available today |
| MySQL | Supported | Available today |
| SQLite | Candidate | Not supported yet |
| SQL Server | Candidate | Not supported yet |
| ClickHouse | Candidate | Not supported yet |

## Product value

`sql-query-mcp` helps AI clients discover schema, sample data, and analyze
read-only queries through one controlled MCP interface.

It keeps connection handling, namespace rules, SQL validation, and audit
logging on the server side, so you can expose useful database context to AI
without exposing raw connection strings or flattening engine-specific concepts.

## What AI can do with it

The current tool set focuses on database discovery and controlled query
workflows. You can use it to help an AI assistant understand structure before
it generates or refines SQL.

MySQL supports `explain_query`, but not `explain_query(..., analyze=True)` in
the current implementation.

| Tool | PostgreSQL | MySQL | Purpose |
| --- | --- | --- | --- |
| `list_connections()` | Yes | Yes | List configured connections |
| `list_schemas(connection_id)` | Yes | No | List visible PostgreSQL schemas |
| `list_databases(connection_id)` | No | Yes | List visible MySQL databases |
| `list_tables(connection_id, schema?, database?)` | Yes | Yes | List tables and views |
| `describe_table(connection_id, table_name, schema?, database?)` | Yes | Yes | Inspect columns, keys, and indexes |
| `run_select(connection_id, sql, limit?)` | Yes | Yes | Run read-only queries |
| `explain_query(connection_id, sql, analyze?)` | Yes | Yes | Inspect query plans |
| `get_table_sample(connection_id, table_name, schema?, database?, limit?)` | Yes | Yes | Fetch small table samples |

These tools are useful for tasks such as listing namespaces, inspecting table
definitions, reviewing indexes, sampling records, and analyzing read-only
queries with `EXPLAIN`. For full request and response details, see
`docs/api-reference.md` (Chinese).

## How boundaries are constrained

The product boundary is intentionally narrow today. Only PostgreSQL and MySQL
are available today, and the current tool set is fully read-only.

The service keeps those boundaries explicit in a few ways.

- Connections declare `engine` explicitly, so the server never guesses from
  `connection_id`.
- PostgreSQL uses `schema`, and MySQL uses `database`, without collapsing both
  into one vague namespace field.
- Real DSNs stay in environment variables, while config files store only the
  environment variable names.
- Query execution passes through `sqlglot` validation before reaching the
  database.
- The server accepts only `SELECT` and `WITH ... SELECT`, rejects comments and
  multi-statement input, and records audit logs for each call.

For MySQL, `explain_query(..., analyze=True)` is not available in the current
implementation.

## Quick start

`sql-query-mcp` supports two official PyPI-based setup modes. Both are intended
for real usage, not just local testing.

1. Choose how you want your MCP client to start the server.

Use installed command mode if you want a simple local command after one
install.

```bash
pipx install sql-query-mcp
```

Use managed launch mode if you want the package source declared directly in
your MCP client config.

```bash
pipx run --spec sql-query-mcp sql-query-mcp
```

Pin a version with `pipx install 'sql-query-mcp==X.Y.Z'` or
`pipx run --spec 'sql-query-mcp==X.Y.Z' sql-query-mcp`. Upgrade installed
command mode with `pipx upgrade sql-query-mcp`.

2. Create a config file.

The server configuration should live outside the repository so the same file
works with either startup mode.

```bash
mkdir -p ~/.config/sql-query-mcp
```

Then save the example JSON later in this section as
`~/.config/sql-query-mcp/connections.json`.

3. Register the server in your MCP client.

- Codex: `docs/codex-setup.md` (Chinese)
- OpenCode: `docs/opencode-setup.md` (Chinese)

Installed command mode means your client runs `sql-query-mcp` directly.
Managed launch mode means your client starts the server through `pipx run`.

In both modes, put `SQL_QUERY_MCP_CONFIG` and your real database DSNs in the
MCP client's environment block instead of exporting them in your shell.

The console entry point is `sql-query-mcp`, which maps to
`sql_query_mcp.app:main`.

The PyPI install name is `sql-query-mcp`, and the Python package import path is
`sql_query_mcp`.

For `pipx install` and `pipx run`, set `SQL_QUERY_MCP_CONFIG` explicitly to
your config file path. The default `config/connections.json` path is mainly for
source checkouts and local development.

The example config looks like this.

```json
{
  "settings": {
    "default_limit": 200,
    "max_limit": 1000,
    "audit_log_path": "logs/audit.jsonl"
  },
  "connections": [
    {
      "connection_id": "crm_prod_main_ro",
      "engine": "postgres",
      "label": "CRM PostgreSQL production / Main / read-only",
      "env": "prod",
      "tenant": "main",
      "role": "ro",
      "dsn_env": "PG_CONN_CRM_PROD_MAIN_RO",
      "enabled": true,
      "default_schema": "public"
    },
    {
      "connection_id": "crm_mysql_prod_main_ro",
      "engine": "mysql",
      "label": "CRM MySQL production / Main / read-only",
      "env": "prod",
      "tenant": "main",
      "role": "ro",
      "dsn_env": "MYSQL_CONN_CRM_PROD_MAIN_RO",
      "enabled": true,
      "default_database": "crm"
    }
  ]
}
```

## Documentation

If you want implementation details, setup guidance, or internal structure, use
these docs as your starting points.

- `docs/project-overview.md`: project goals, concepts, and code structure (Chinese)
- `docs/api-reference.md`: MCP tool reference (Chinese)
- `docs/codex-setup.md`: Codex setup steps (Chinese)
- `docs/opencode-setup.md`: OpenCode setup steps (Chinese)
- `docs/release-process.md`: PyPI and GitHub Release workflow (Chinese)
- `docs/git-workflow.md`: repository collaboration workflow (Chinese)

## Development

If you want to modify or verify the project locally, use this shortest path.
Editable install remains the development path, and the local environment still
requires Python 3.10+.

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
PYTHONPATH=. python3 -m unittest discover -s tests
```

The main entry point is `sql_query_mcp/app.py`. Core modules include:

- `sql_query_mcp/config.py`: config loading and validation
- `sql_query_mcp/validator.py`: read-only SQL validation
- `sql_query_mcp/introspection.py`: metadata inspection
- `sql_query_mcp/executor.py`: query execution and limits
- `sql_query_mcp/adapters/`: PostgreSQL and MySQL adapters

## Contributing

If you want to contribute or review the repository workflow, start with these
pages.

- `CONTRIBUTING.md`
- `docs/roadmap.md`
- `docs/git-workflow.md` (Chinese)

Run `PYTHONPATH=. python3 -m unittest discover -s tests` before you submit
changes.

## License

This project is released under the MIT License. See `LICENSE`.