"""Query execution helpers."""

from __future__ import annotations

import time
from typing import Dict, Optional

from .audit import AuditLogger
from .config import ServerSettings
from .errors import QueryExecutionError, sanitize_error_message
from .namespace import resolve_namespace
from .registry import ConnectionRegistry
from .validator import (
    build_limited_query,
    clamp_limit,
    summarize_sql,
    validate_select_sql,
)


class QueryExecutor:
    """Execute validated read-only SQL."""

    def __init__(
        self,
        registry: ConnectionRegistry,
        settings: ServerSettings,
        audit_logger: AuditLogger,
    ):
        self._registry = registry
        self._settings = settings
        self._audit = audit_logger

    def run_select(
        self, connection_id: str, sql_text: str, limit: Optional[int] = None
    ) -> Dict[str, object]:
        cleaned_sql = validate_select_sql(sql_text)
        row_limit = clamp_limit(limit, self._settings.default_limit, self._settings.max_limit)
        limited_sql, _ = build_limited_query(cleaned_sql, row_limit)
        sql_summary = summarize_sql(cleaned_sql)
        started = time.perf_counter()
        config = None

        try:
            config = self._registry.get_connection_config(connection_id)
            with self._registry.connection_from_config(config) as (conn, adapter):
                adapter.set_statement_timeout(conn, self._settings.statement_timeout_ms)
                with conn.cursor() as cur:
                    cur.execute(limited_sql)
                    columns = adapter.column_names(cur.description)
                    rows = cur.fetchall()

                truncated = len(rows) > row_limit
                trimmed_rows = rows[:row_limit]
                duration_ms = _elapsed_ms(started)
                self._audit.log(
                    tool="run_select",
                    connection_id=connection_id,
                    success=True,
                    duration_ms=duration_ms,
                    row_count=len(trimmed_rows),
                    sql_summary=sql_summary,
                    extra={"engine": config.engine, "limit": row_limit, "truncated": truncated},
                )
                return {
                    "connection_id": connection_id,
                    "engine": config.engine,
                    "columns": columns,
                    "rows": trimmed_rows,
                    "row_count": len(trimmed_rows),
                    "truncated": truncated,
                    "duration_ms": duration_ms,
                    "applied_limit": row_limit,
                }
        except Exception as exc:
            duration_ms = _elapsed_ms(started)
            sanitized = sanitize_error_message(str(exc))
            self._audit.log(
                tool="run_select",
                connection_id=connection_id,
                success=False,
                duration_ms=duration_ms,
                sql_summary=sql_summary,
                error=sanitized,
                extra=_build_audit_extra(config, limit=row_limit),
            )
            raise QueryExecutionError(sanitized) from exc

    def explain_query(
        self, connection_id: str, sql_text: str, analyze: bool = False
    ) -> Dict[str, object]:
        cleaned_sql = validate_select_sql(sql_text)
        sql_summary = summarize_sql(cleaned_sql)
        started = time.perf_counter()
        config = None
        try:
            config = self._registry.get_connection_config(connection_id)
            adapter = self._registry.get_adapter(config)
            explain_sql = adapter.build_explain_query(cleaned_sql, analyze=analyze)
            with self._registry.connection_from_config(config) as (conn, adapter):
                adapter.set_statement_timeout(conn, self._settings.statement_timeout_ms)
                with conn.cursor() as cur:
                    cur.execute(explain_sql)
                    rows = cur.fetchall()

                duration_ms = _elapsed_ms(started)
                plan = adapter.extract_plan(rows)
                self._audit.log(
                    tool="explain_query",
                    connection_id=connection_id,
                    success=True,
                    duration_ms=duration_ms,
                    row_count=1 if rows else 0,
                    sql_summary=sql_summary,
                    extra={"engine": config.engine, "analyze": analyze},
                )
                return {
                    "connection_id": connection_id,
                    "engine": config.engine,
                    "plan": plan,
                    "duration_ms": duration_ms,
                    "analyze": analyze,
                }
        except Exception as exc:
            duration_ms = _elapsed_ms(started)
            sanitized = sanitize_error_message(str(exc))
            self._audit.log(
                tool="explain_query",
                connection_id=connection_id,
                success=False,
                duration_ms=duration_ms,
                sql_summary=sql_summary,
                error=sanitized,
                extra=_build_audit_extra(config, analyze=analyze),
            )
            raise QueryExecutionError(sanitized) from exc

    def get_table_sample(
        self,
        connection_id: str,
        table_name: str,
        schema: Optional[str] = None,
        database: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, object]:
        row_limit = clamp_limit(limit, self._settings.default_limit, self._settings.max_limit)
        started = time.perf_counter()
        config = None
        try:
            config = self._registry.get_connection_config(connection_id)
            namespace = resolve_namespace(config, schema=schema, database=database)
            adapter = self._registry.get_adapter(config)
            query = adapter.build_sample_query(namespace.value, table_name, row_limit + 1)
            with self._registry.connection_from_config(config) as (conn, adapter):
                adapter.set_statement_timeout(conn, self._settings.statement_timeout_ms)
                with conn.cursor() as cur:
                    cur.execute(query)
                    columns = adapter.column_names(cur.description)
                    rows = cur.fetchall()

                truncated = len(rows) > row_limit
                trimmed_rows = rows[:row_limit]
                duration_ms = _elapsed_ms(started)
                self._audit.log(
                    tool="get_table_sample",
                    connection_id=connection_id,
                    success=True,
                    duration_ms=duration_ms,
                    row_count=len(trimmed_rows),
                    sql_summary=f"sample {namespace.value}.{table_name}",
                    extra={
                        "engine": config.engine,
                        namespace.field_name: namespace.value,
                        "table_name": table_name,
                        "limit": row_limit,
                    },
                )
                return {
                    "connection_id": connection_id,
                    "engine": config.engine,
                    namespace.field_name: namespace.value,
                    "table_name": table_name,
                    "columns": columns,
                    "rows": trimmed_rows,
                    "row_count": len(trimmed_rows),
                    "truncated": truncated,
                    "duration_ms": duration_ms,
                    "applied_limit": row_limit,
                }
        except Exception as exc:
            duration_ms = _elapsed_ms(started)
            sanitized = sanitize_error_message(str(exc))
            self._audit.log(
                tool="get_table_sample",
                connection_id=connection_id,
                success=False,
                duration_ms=duration_ms,
                error=sanitized,
                extra=_build_audit_extra(
                    config,
                    schema=schema,
                    database=database,
                    table_name=table_name,
                    limit=row_limit,
                ),
            )
            raise QueryExecutionError(sanitized) from exc


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _build_audit_extra(config, **kwargs: object) -> Dict[str, object]:
    extra = dict(kwargs)
    if config is not None:
        extra["engine"] = config.engine
    return extra
