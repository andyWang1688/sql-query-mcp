# sql-query-mcp

`sql-query-mcp` is a read-only MCP server for PostgreSQL and MySQL. It gives
AI clients a controlled way to inspect database structure, fetch small data
samples, run validated read-only queries, and inspect execution plans without
putting raw DSNs or write access directly in the client.

It is intentionally narrow in scope. PostgreSQL and MySQL are supported now.
Other database adapters are not yet supported.

## What you can do

The current release exposes eight public tools for metadata discovery, sampling,
read-only querying, and plan inspection.

| Tool | PostgreSQL | MySQL | Purpose |
| --- | --- | --- | --- |
| `list_connections` | Yes | Yes | List configured connections |
| `list_schemas` | Yes | No | List visible PostgreSQL schemas |
| `list_databases` | No | Yes | List visible MySQL databases |
| `list_tables` | Yes | Yes | List tables and views in a schema or database |
| `describe_table` | Yes | Yes | Describe columns, keys, and indexes |
| `run_select` | Yes | Yes | Run a validated read-only query |
| `explain_query` | Yes | Yes | Run server-managed `EXPLAIN` for a query |
| `get_table_sample` | Yes | Yes | Fetch a small sample from a table |

The API keeps PostgreSQL and MySQL terms explicit, so callers can use the same
names they already see in each database:

- PostgreSQL tools use `schema`
- MySQL tools use `database`
- Each connection must declare its `engine` explicitly

For full request and response details, see the
[API reference](docs/api-reference.md).

## Quick start

If you want to get the server running first, complete the minimal setup below.

1. Create a virtual environment and install the package.

```bash
cd /absolute/path/to/sql-query-mcp
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

2. Copy the example connection config.

```bash
cp config/connections.example.json config/connections.json
```

3. Export your database DSNs as environment variables.

These example names match the copied `config/connections.example.json` file.

```bash
export PG_CONN_CRM_PROD_MUQIAO_RO='postgresql://user:password@host:5432/dbname'
export MYSQL_CONN_CRM_PROD_MUQIAO_RO='mysql://user:password@host:3306/crm'
export SQL_QUERY_MCP_CONFIG='/absolute/path/to/sql-query-mcp/config/connections.json'
```

4. Register the server in your MCP client.

- [Codex setup](docs/codex-setup.md)
- [OpenCode setup](docs/opencode-setup.md)

The console entry point is `sql-query-mcp`, which maps to
`sql_query_mcp.app:main`.

## Configuration summary

The server reads `config/connections.json` by default. To use a different file,
set `SQL_QUERY_MCP_CONFIG`.

```json
{
  "settings": {
    "default_limit": 200,
    "max_limit": 1000,
    "audit_log_path": "logs/audit.jsonl",
    "statement_timeout_ms": 15000
  },
  "connections": [
    {
      "connection_id": "crm_prod_main_ro",
      "engine": "postgres",
      "label": "CRM PostgreSQL production read-only",
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
      "label": "CRM MySQL production read-only",
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

Key rules:

- Store the real DSN in environment variables, not in `connections.json`
- Use `default_schema` for PostgreSQL connections
- Use `default_database` for MySQL connections
- Keep the database account itself read-only; this server does not replace
  database permissions

## Safety model

The server is designed to keep the database access path narrow and predictable.
Its safeguards are explicit, server-side checks rather than prompt-only rules.

- `run_select` and `explain_query` validate SQL with `sqlglot` AST parsing
- Only `SELECT` and `WITH ... SELECT` statements are accepted
- SQL comments and multi-statement input are rejected
- Mutating statements such as `INSERT`, `UPDATE`, `DELETE`, `DROP`, and
  transaction control statements are rejected
- Requested row counts are clamped to configured limits
- `explain_query` wraps the input query on the server; callers do not pass raw
  `EXPLAIN ...` statements
- MySQL does not support `analyze=True` for `explain_query`

Audit logging covers the metadata and query paths, including metadata lookups,
`run_select`, `explain_query`, and `get_table_sample`. `list_connections` is
outside that path.

## Documentation

Start with these pages if you want the architecture, API contract, or client
setup details.

- [Project overview](docs/project-overview.md)
- [API reference](docs/api-reference.md)
- [Codex setup](docs/codex-setup.md)
- [OpenCode setup](docs/opencode-setup.md)
- [Chinese overview](docs/README.zh-CN.md)

## Contributing and roadmap

If you want to contribute or understand what is planned next, start with these
project-level pages.

- [Contribution guide](CONTRIBUTING.md)
- [Roadmap](docs/roadmap.md)

## License

This project is released under the MIT License.
