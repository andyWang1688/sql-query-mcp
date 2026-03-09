"""Query execution helpers."""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from psycopg import sql

from .audit import AuditLogger
from .config import ServerSettings
from .errors import QueryExecutionError, sanitize_error_message
from .registry import ConnectionRegistry
from .validator import (
    build_explain_query,
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

        try:
            with self._registry.connection(connection_id) as (conn, _):
                _set_statement_timeout(conn, self._settings.statement_timeout_ms)
                with conn.cursor() as cur:
                    cur.execute(limited_sql)
                    columns = [column.name for column in (cur.description or [])]
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
                    extra={"limit": row_limit, "truncated": truncated},
                )
                return {
                    "connection_id": connection_id,
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
                extra={"limit": row_limit},
            )
            raise QueryExecutionError(sanitized) from exc

    def explain_query(
        self, connection_id: str, sql_text: str, analyze: bool = False
    ) -> Dict[str, object]:
        cleaned_sql = validate_select_sql(sql_text)
        explain_sql = build_explain_query(cleaned_sql, analyze=analyze)
        sql_summary = summarize_sql(cleaned_sql)
        started = time.perf_counter()
        try:
            with self._registry.connection(connection_id) as (conn, _):
                _set_statement_timeout(conn, self._settings.statement_timeout_ms)
                with conn.cursor() as cur:
                    cur.execute(explain_sql)
                    rows = cur.fetchall()

                duration_ms = _elapsed_ms(started)
                plan = rows[0]["QUERY PLAN"] if rows else []
                self._audit.log(
                    tool="explain_query",
                    connection_id=connection_id,
                    success=True,
                    duration_ms=duration_ms,
                    row_count=1 if rows else 0,
                    sql_summary=sql_summary,
                    extra={"analyze": analyze},
                )
                return {
                    "connection_id": connection_id,
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
                extra={"analyze": analyze},
            )
            raise QueryExecutionError(sanitized) from exc

    def get_table_sample(
        self,
        connection_id: str,
        table_name: str,
        schema: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, object]:
        row_limit = clamp_limit(limit, self._settings.default_limit, self._settings.max_limit)
        started = time.perf_counter()
        try:
            with self._registry.connection(connection_id) as (conn, config):
                resolved_schema = schema or config.default_schemas[0]
                _set_statement_timeout(conn, self._settings.statement_timeout_ms)
                query = sql.SQL("SELECT * FROM {}.{} LIMIT {}").format(
                    sql.Identifier(resolved_schema),
                    sql.Identifier(table_name),
                    sql.Literal(row_limit + 1),
                )
                with conn.cursor() as cur:
                    cur.execute(query)
                    columns = [column.name for column in (cur.description or [])]
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
                    sql_summary=f"sample {resolved_schema}.{table_name}",
                    extra={"schema": resolved_schema, "table_name": table_name, "limit": row_limit},
                )
                return {
                    "connection_id": connection_id,
                    "schema": resolved_schema,
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
                extra={"schema": schema, "table_name": table_name, "limit": row_limit},
            )
            raise QueryExecutionError(sanitized) from exc


def _set_statement_timeout(conn, timeout_ms: int) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('statement_timeout', %s, false)", (str(timeout_ms),))


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
