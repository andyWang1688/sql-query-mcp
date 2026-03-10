"""FastMCP application for stateless SQL queries."""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from .audit import AuditLogger
from .config import load_config
from .errors import SqlQueryMCPError
from .executor import QueryExecutor
from .introspection import MetadataService
from .registry import ConnectionRegistry


def create_app() -> FastMCP:
    app_config = load_config()
    registry = ConnectionRegistry(app_config)
    audit_logger = AuditLogger(app_config.settings.audit_log_path)
    metadata = MetadataService(registry, app_config.settings, audit_logger)
    executor = QueryExecutor(registry, app_config.settings, audit_logger)

    mcp = FastMCP("sql-query-mcp", json_response=True)

    @mcp.tool()
    def list_connections() -> dict:
        """List configured SQL connections by connection_id."""

        return {"connections": registry.list_connections()}

    @mcp.tool()
    def list_schemas(connection_id: str) -> dict:
        """List visible schemas for a PostgreSQL connection."""

        return _run_tool(lambda: metadata.list_schemas(connection_id))

    @mcp.tool()
    def list_databases(connection_id: str) -> dict:
        """List visible databases for a MySQL connection."""

        return _run_tool(lambda: metadata.list_databases(connection_id))

    @mcp.tool()
    def list_tables(
        connection_id: str,
        schema: Optional[str] = None,
        database: Optional[str] = None,
    ) -> dict:
        """List tables and views for a resolved PostgreSQL schema or MySQL database."""

        return _run_tool(lambda: metadata.list_tables(connection_id, schema, database))

    @mcp.tool()
    def describe_table(
        connection_id: str,
        table_name: str,
        schema: Optional[str] = None,
        database: Optional[str] = None,
    ) -> dict:
        """Describe columns, keys, and indexes for a table."""

        return _run_tool(lambda: metadata.describe_table(connection_id, table_name, schema, database))

    @mcp.tool()
    def run_select(connection_id: str, sql: str, limit: Optional[int] = None) -> dict:
        """Run a read-only SELECT or CTE query."""

        return _run_tool(lambda: executor.run_select(connection_id, sql, limit))

    @mcp.tool()
    def explain_query(connection_id: str, sql: str, analyze: bool = False) -> dict:
        """Run EXPLAIN on a read-only SELECT or CTE query."""

        return _run_tool(lambda: executor.explain_query(connection_id, sql, analyze))

    @mcp.tool()
    def get_table_sample(
        connection_id: str,
        table_name: str,
        schema: Optional[str] = None,
        database: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """Fetch a small sample from a table for schema discovery."""

        return _run_tool(lambda: executor.get_table_sample(connection_id, table_name, schema, database, limit))

    return mcp


def _run_tool(func):
    try:
        return func()
    except SqlQueryMCPError as exc:
        raise ValueError(str(exc)) from exc


def main() -> None:
    app = create_app()
    app.run()


if __name__ == "__main__":
    main()
