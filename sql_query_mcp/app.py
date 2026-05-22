"""FastMCP application for stateless SQL queries."""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from .async_queries import AsyncQueryService
from .audit import AuditLogger
from .config import load_config
from .errors import SqlQueryMCPError
from .executor import QueryExecutor
from .exporter import QueryExporter
from .importer import TableFileImporter
from .introspection import MetadataService
from .registry import ConnectionRegistry


def create_app() -> FastMCP:
    app_config = load_config()
    registry = ConnectionRegistry(app_config)
    audit_logger = AuditLogger(app_config.settings.audit_log_path)
    metadata = MetadataService(registry, app_config.settings, audit_logger)
    executor = QueryExecutor(registry, app_config.settings, audit_logger)
    exporter = QueryExporter(registry, app_config.settings, audit_logger)
    importer = TableFileImporter(registry, app_config.settings, audit_logger)
    async_queries = AsyncQueryService(registry, app_config.settings, audit_logger)

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
        """List visible databases for a MySQL or Hive connection."""

        return _run_tool(lambda: metadata.list_databases(connection_id))

    @mcp.tool()
    def list_tables(
        connection_id: str,
        schema: Optional[str] = None,
        database: Optional[str] = None,
    ) -> dict:
        """List tables and views for a resolved schema or database."""

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

    @mcp.tool()
    def export_query_file(
        connection_id: str,
        sql: str,
        output_path: str,
        format: str = "csv",
        limit: Optional[int] = 1000,
        export_all: bool = False,
        file_name: Optional[str] = None,
        overwrite: bool = False,
    ) -> dict:
        """Export a read-only query result to a local CSV or XLSX file."""

        return _run_tool(
            lambda: exporter.export_query_file(
                connection_id,
                sql,
                output_path,
                format,
                limit,
                export_all,
                file_name,
                overwrite,
            )
        )

    @mcp.tool()
    def start_query(connection_id: str, sql: str, limit: Optional[int] = None) -> dict:
        """Start an asynchronous read-only SELECT or CTE query."""

        return _run_tool(lambda: async_queries.start_query(connection_id, sql, limit))

    @mcp.tool()
    def get_query(query_id: str, offset: int = 0, limit: Optional[int] = None) -> dict:
        """Get asynchronous query status and paginated results when complete."""

        return _run_tool(lambda: async_queries.get_query(query_id, offset, limit))

    @mcp.tool()
    def cancel_query(query_id: str) -> dict:
        """Cancel a running asynchronous query."""

        return _run_tool(lambda: async_queries.cancel_query(query_id))

    @mcp.tool()
    def import_table_file(
        connection_id: str,
        table_name: str,
        file_path: str,
        schema: Optional[str] = None,
        database: Optional[str] = None,
        sheet_name: Optional[str] = None,
    ) -> dict:
        """Import a local CSV or XLSX file into an existing table."""

        return _run_tool(
            lambda: importer.import_table_file(
                connection_id,
                table_name,
                file_path,
                schema,
                database,
                sheet_name,
            )
        )

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
