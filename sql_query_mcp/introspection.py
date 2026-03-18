"""Metadata query helpers."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from .audit import AuditLogger
from .config import ServerSettings
from .errors import QueryExecutionError, sanitize_error_message
from .namespace import require_engine, resolve_namespace
from .registry import ConnectionRegistry


class MetadataService:
    """Read-only metadata queries across PostgreSQL and MySQL."""

    def __init__(
        self,
        registry: ConnectionRegistry,
        settings: ServerSettings,
        audit_logger: AuditLogger,
    ):
        self._registry = registry
        self._settings = settings
        self._audit = audit_logger

    def list_schemas(self, connection_id: str) -> Dict[str, object]:
        started = time.perf_counter()
        config = None
        try:
            config = self._registry.get_connection_config(connection_id)
            require_engine(config, "postgres", "list_schemas")
            with self._registry.connection_from_config(config) as (conn, adapter):
                _apply_statement_timeout(
                    adapter, conn, self._settings.statement_timeout_ms
                )
                schemas = adapter.list_schemas(conn)
            duration_ms = _elapsed_ms(started)
            self._audit.log(
                tool="list_schemas",
                connection_id=connection_id,
                success=True,
                duration_ms=duration_ms,
                row_count=len(schemas),
                extra={"engine": config.engine},
            )
            return {
                "connection_id": connection_id,
                "engine": "postgres",
                "schemas": schemas,
            }
        except Exception as exc:
            duration_ms = _elapsed_ms(started)
            sanitized = sanitize_error_message(str(exc))
            self._audit.log(
                tool="list_schemas",
                connection_id=connection_id,
                success=False,
                duration_ms=duration_ms,
                error=sanitized,
                extra=_build_audit_extra(config),
            )
            raise QueryExecutionError(sanitized) from exc

    def list_databases(self, connection_id: str) -> Dict[str, object]:
        started = time.perf_counter()
        config = None
        try:
            config = self._registry.get_connection_config(connection_id)
            require_engine(config, "mysql", "list_databases")
            with self._registry.connection_from_config(config) as (conn, adapter):
                _apply_statement_timeout(
                    adapter, conn, self._settings.statement_timeout_ms
                )
                databases = adapter.list_databases(conn)
            duration_ms = _elapsed_ms(started)
            self._audit.log(
                tool="list_databases",
                connection_id=connection_id,
                success=True,
                duration_ms=duration_ms,
                row_count=len(databases),
                extra={"engine": config.engine},
            )
            return {
                "connection_id": connection_id,
                "engine": "mysql",
                "databases": databases,
            }
        except Exception as exc:
            duration_ms = _elapsed_ms(started)
            sanitized = sanitize_error_message(str(exc))
            self._audit.log(
                tool="list_databases",
                connection_id=connection_id,
                success=False,
                duration_ms=duration_ms,
                error=sanitized,
                extra=_build_audit_extra(config),
            )
            raise QueryExecutionError(sanitized) from exc

    def list_tables(
        self,
        connection_id: str,
        schema: Optional[str] = None,
        database: Optional[str] = None,
    ) -> Dict[str, object]:
        started = time.perf_counter()
        config = None
        try:
            config = self._registry.get_connection_config(connection_id)
            namespace = resolve_namespace(config, schema=schema, database=database)
            with self._registry.connection_from_config(config) as (conn, adapter):
                _apply_statement_timeout(
                    adapter, conn, self._settings.statement_timeout_ms
                )
                tables = adapter.list_tables(conn, namespace.value)
            duration_ms = _elapsed_ms(started)
            self._audit.log(
                tool="list_tables",
                connection_id=connection_id,
                success=True,
                duration_ms=duration_ms,
                row_count=len(tables),
                extra={"engine": config.engine, namespace.field_name: namespace.value},
            )
            return {
                "connection_id": connection_id,
                "engine": config.engine,
                namespace.field_name: namespace.value,
                "tables": tables,
            }
        except Exception as exc:
            duration_ms = _elapsed_ms(started)
            sanitized = sanitize_error_message(str(exc))
            self._audit.log(
                tool="list_tables",
                connection_id=connection_id,
                success=False,
                duration_ms=duration_ms,
                error=sanitized,
                extra=_build_audit_extra(config, schema=schema, database=database),
            )
            raise QueryExecutionError(sanitized) from exc

    def describe_table(
        self,
        connection_id: str,
        table_name: str,
        schema: Optional[str] = None,
        database: Optional[str] = None,
    ) -> Dict[str, object]:
        started = time.perf_counter()
        config = None
        try:
            config = self._registry.get_connection_config(connection_id)
            namespace = resolve_namespace(config, schema=schema, database=database)
            with self._registry.connection_from_config(config) as (conn, adapter):
                _apply_statement_timeout(
                    adapter, conn, self._settings.statement_timeout_ms
                )
                description = adapter.describe_table(conn, namespace.value, table_name)
                if not description:
                    raise QueryExecutionError(
                        f"未找到表 {namespace.value}.{table_name}，或当前用户没有访问权限"
                    )

            duration_ms = _elapsed_ms(started)
            self._audit.log(
                tool="describe_table",
                connection_id=connection_id,
                success=True,
                duration_ms=duration_ms,
                row_count=len(description["columns"]),
                extra={
                    "engine": config.engine,
                    namespace.field_name: namespace.value,
                    "table_name": table_name,
                },
            )
            return {
                "connection_id": connection_id,
                "engine": config.engine,
                namespace.field_name: namespace.value,
                "table_name": table_name,
                "columns": description["columns"],
                "indexes": description["indexes"],
            }
        except Exception as exc:
            duration_ms = _elapsed_ms(started)
            sanitized = sanitize_error_message(str(exc))
            self._audit.log(
                tool="describe_table",
                connection_id=connection_id,
                success=False,
                duration_ms=duration_ms,
                error=sanitized,
                extra=_build_audit_extra(
                    config,
                    schema=schema,
                    database=database,
                    table_name=table_name,
                ),
            )
            raise QueryExecutionError(sanitized) from exc


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _apply_statement_timeout(
    adapter: Any, conn: Any, timeout_ms: Optional[int]
) -> None:
    if timeout_ms is not None:
        getattr(adapter, "set_statement_timeout")(conn, timeout_ms)


def _build_audit_extra(config, **kwargs: object) -> Dict[str, object]:
    extra = dict(kwargs)
    if config is not None:
        extra["engine"] = config.engine
    return extra
