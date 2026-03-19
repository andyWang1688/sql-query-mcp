# Adapter development

This page explains how database adapters fit into `sql-query-mcp`, which
methods the current code calls on an adapter, and what you need to implement if
you want to propose a new one. Current runtime support remains PostgreSQL and
MySQL only, so treat any work on other engines as a candidate contribution
until the project accepts it.

## Where adapters live

Adapter implementations live in `sql_query_mcp/adapters/`. The current runtime
adapters are `sql_query_mcp/adapters/postgres.py` and
`sql_query_mcp/adapters/mysql.py`.

- `sql_query_mcp/adapters/postgres.py` implements PostgreSQL-specific metadata,
  sampling, explain formatting, connection pooling, and result handling.
- `sql_query_mcp/adapters/mysql.py` implements MySQL-specific metadata,
  sampling, explain formatting, DSN parsing, and result handling.
- `sql_query_mcp/adapters/__init__.py` exposes `PostgresAdapter` and
  `MySQLAdapter` through package-level imports.
- `sql_query_mcp/registry.py` instantiates adapters and routes each configured
  connection to the correct engine implementation.

## What adapters interact with

An adapter is not a standalone plugin. It works inside the code that opens a
database connection, serves metadata tools, executes read-only queries, and
records audit logs for each request.

- `sql_query_mcp/registry.py` maps `config.engine` values to adapter instances
  and opens connections by engine.
- `sql_query_mcp/introspection.py` calls adapter methods for metadata tools,
  such as listing namespaces, tables, and table descriptions.
- `sql_query_mcp/executor.py` uses adapter methods to build sample queries,
  format `EXPLAIN`, extract plans, and normalize column names.
- The adapter must preserve current engine-specific behavior instead of forcing
  a fake universal namespace model.

## Adapter API you need to implement

Before you start a candidate adapter, study the practical method surface that
the current code already relies on. `ConnectionRegistry`, `MetadataService`,
and `QueryExecutor` call adapter methods directly, so a new adapter must match
that behavior.

The current adapter API includes the following members.

| Member | Called from | What it needs to do |
| --- | --- | --- |
| `connection(connection_id, dsn)` | `sql_query_mcp/registry.py` | Open a database connection with a context manager and yield a live connection object. |
| `close()` | `sql_query_mcp/registry.py` | Clean up pooled or cached resources when the registry shuts down. |
| `set_statement_timeout(conn, timeout_ms)` | `sql_query_mcp/introspection.py`, `sql_query_mcp/executor.py` | Apply the per-request statement timeout if one is configured. |
| `list_schemas(conn)` | `sql_query_mcp/introspection.py` for PostgreSQL | Return visible PostgreSQL schemas. This is engine-specific. |
| `list_databases(conn)` | `sql_query_mcp/introspection.py` for MySQL | Return visible MySQL databases. This is engine-specific. |
| `list_tables(conn, namespace)` | `sql_query_mcp/introspection.py` | Return tables and views for the resolved schema or database. |
| `describe_table(conn, namespace, table_name)` | `sql_query_mcp/introspection.py` | Return normalized column and index metadata, or `None` when the table is not found. |
| `build_sample_query(namespace, table_name, sentinel_limit)` | `sql_query_mcp/executor.py` | Build a safe sample query that fetches one extra row so truncation can be detected. |
| `build_explain_query(sql_text, analyze=False)` | `sql_query_mcp/executor.py` | Wrap a validated read-only query in the engine's `EXPLAIN` form and reject unsupported options when needed. |
| `extract_plan(rows)` | `sql_query_mcp/executor.py` | Convert raw `EXPLAIN` rows into the `plan` value returned by the tool. |
| `column_names(description)` | `sql_query_mcp/executor.py` | Normalize cursor description output into a list of column names. |

## What contributors need to implement

If you propose a candidate adapter, implement the same integration points that
the PostgreSQL and MySQL adapters already satisfy. Keep behavior read-only, and
avoid broadening runtime support claims until the project has accepted the new
engine.

1. Add an adapter module under `sql_query_mcp/adapters/`.
2. Update `sql_query_mcp/adapters/__init__.py` to expose the new adapter. The
   current registry imports adapters from the package with
   `from .adapters import MySQLAdapter, PostgresAdapter`, so the package export
   file must include any newly supported adapter class.
3. Register the engine in `sql_query_mcp/registry.py` so configured
   connections resolve to the new adapter.
4. Implement connection handling, statement timeout handling, metadata access,
   sample query generation, explain query generation, plan extraction, and
   column name normalization.
5. Preserve engine-native namespace semantics. For example, PostgreSQL uses
   `schema`, and MySQL uses `database`; a future candidate adapter must define
   its own compatible namespace behavior clearly.
6. Keep the adapter compatible with `sql_query_mcp/introspection.py` and
   `sql_query_mcp/executor.py` without weakening read-only validation or the
   audit log fields those services already write.

## Practical behavior to study

The existing adapters show more than method names. They show the return shapes
and edge cases that the rest of the project already expects.

- In `sql_query_mcp/adapters/postgres.py`, study how `describe_table()` returns
  `columns` and `indexes`, how `build_sample_query()` quotes identifiers with
  `psycopg.sql`, and how `build_explain_query()` returns JSON-format plans.
- In `sql_query_mcp/adapters/mysql.py`, study how `describe_table()` normalizes
  MySQL metadata, how `build_explain_query()` rejects `analyze=True`, and how
  `extract_plan()` parses JSON text from MySQL's `EXPLAIN` output.
- In `sql_query_mcp/registry.py`, study how adapter instances are created once
  and reused from the `_adapters` map.
- In `sql_query_mcp/introspection.py`, study how missing table metadata is
  turned into a `QueryExecutionError` and how timeout and audit logging happen
  around adapter calls.
- In `sql_query_mcp/executor.py`, study how sample queries detect truncation,
  how validated SQL is wrapped for `EXPLAIN`, and how column names and rows are
  returned to tool callers.

## What contributors need to test

Adapter work needs tests at the layer users actually hit through the MCP tools,
not only tests inside the adapter module. The existing test suite shows the
behavior that must remain stable when a new engine is introduced.

- Use `tests/test_metadata.py` as a reference for metadata service behavior,
  namespace validation, and engine-specific restrictions.
- Use `tests/test_executor.py` as a reference for executor behavior, explain
  handling, sample query behavior, and connection-avoidance checks on invalid
  input.
- Add tests for success paths and failure paths, including unsupported
  namespace combinations and engine-specific `EXPLAIN` behavior.
- Verify that audit logs and error responses still match what
  `sql_query_mcp/introspection.py` and `sql_query_mcp/executor.py` currently
  produce.

## Contribution flow

Because adapter work changes long-term scope, start with project process before
implementation. The contribution and Git workflow docs define how to propose,
branch, test, and submit the change.

1. Open or join an issue as described in
   [the contribution guide](../CONTRIBUTING.md).
2. Confirm branch and pull request expectations in
   [the Git workflow guide](git-workflow.md).
3. Keep documentation updated so [the roadmap](roadmap.md) and other affected
   pages reflect the accepted list of supported databases.

## Next steps

If you want to contribute a candidate adapter, align on scope before touching
runtime support claims.

1. Review [the roadmap](roadmap.md) for the current list of supported
   databases and future candidate examples.
2. Read [the contribution guide](../CONTRIBUTING.md) before opening
   implementation work.
3. Follow [the Git workflow guide](git-workflow.md) when you prepare your
   branch.
