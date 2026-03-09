"""FastMCP application for stateless PostgreSQL queries."""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from .audit import AuditLogger
from .config import load_config
from .errors import PostgresQueryMCPError
from .executor import QueryExecutor
from .introspection import IntrospectionService
from .registry import ConnectionRegistry


def create_app() -> FastMCP:
    app_config = load_config()
    registry = ConnectionRegistry(app_config)
    audit_logger = AuditLogger(app_config.settings.audit_log_path)
    introspection = IntrospectionService(registry, app_config.settings, audit_logger)
    executor = QueryExecutor(registry, app_config.settings, audit_logger)

    mcp = FastMCP("postgres-query-mcp", json_response=True)

    @mcp.tool()
    def list_connections() -> dict:
        """List configured PostgreSQL connections by connection_id."""

        return {"connections": registry.list_connections()}

    @mcp.tool()
    def list_schemas(connection_id: str) -> dict:
        """List visible schemas for a configured PostgreSQL connection."""

        return _run_tool(lambda: introspection.list_schemas(connection_id))

    @mcp.tool()
    def list_tables(connection_id: str, schema: Optional[str] = None) -> dict:
        """List tables and views, optionally filtered by schema."""

        return _run_tool(lambda: introspection.list_tables(connection_id, schema))

    @mcp.tool()
    def describe_table(
        connection_id: str, table_name: str, schema: Optional[str] = None
    ) -> dict:
        """Describe columns, keys, and indexes for a table."""

        return _run_tool(lambda: introspection.describe_table(connection_id, table_name, schema))

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
        limit: Optional[int] = None,
    ) -> dict:
        """Fetch a small sample from a table for schema discovery."""

        return _run_tool(lambda: executor.get_table_sample(connection_id, table_name, schema, limit))

    return mcp


def _run_tool(func):
    try:
        return func()
    except PostgresQueryMCPError as exc:
        raise ValueError(str(exc)) from exc


def main() -> None:
    app = create_app()
    app.run()


if __name__ == "__main__":
    main()
