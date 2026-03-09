"""Schema and table introspection helpers."""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from .audit import AuditLogger
from .config import ServerSettings
from .errors import QueryExecutionError, sanitize_error_message
from .registry import ConnectionRegistry


class IntrospectionService:
    """Read-only metadata queries."""

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
        query = """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('information_schema')
              AND schema_name NOT LIKE 'pg_%'
            ORDER BY schema_name
        """
        started = time.perf_counter()
        try:
            rows = self._fetch_rows(connection_id, query)
            duration_ms = _elapsed_ms(started)
            self._audit.log(
                tool="list_schemas",
                connection_id=connection_id,
                success=True,
                duration_ms=duration_ms,
                row_count=len(rows),
            )
            return {"connection_id": connection_id, "schemas": [row["schema_name"] for row in rows]}
        except Exception as exc:
            duration_ms = _elapsed_ms(started)
            sanitized = sanitize_error_message(str(exc))
            self._audit.log(
                tool="list_schemas",
                connection_id=connection_id,
                success=False,
                duration_ms=duration_ms,
                error=sanitized,
            )
            raise QueryExecutionError(sanitized) from exc

    def list_tables(self, connection_id: str, schema: Optional[str] = None) -> Dict[str, object]:
        query = """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema')
              AND table_schema NOT LIKE 'pg_%'
        """
        params = []
        if schema:
            query += " AND table_schema = %s"
            params.append(schema)
        query += " ORDER BY table_schema, table_name"

        started = time.perf_counter()
        try:
            rows = self._fetch_rows(connection_id, query, params)
            duration_ms = _elapsed_ms(started)
            self._audit.log(
                tool="list_tables",
                connection_id=connection_id,
                success=True,
                duration_ms=duration_ms,
                row_count=len(rows),
                extra={"schema": schema},
            )
            return {
                "connection_id": connection_id,
                "schema": schema,
                "tables": rows,
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
                extra={"schema": schema},
            )
            raise QueryExecutionError(sanitized) from exc

    def describe_table(
        self, connection_id: str, table_name: str, schema: Optional[str] = None
    ) -> Dict[str, object]:
        started = time.perf_counter()
        try:
            with self._registry.connection(connection_id) as (conn, config):
                resolved_schema = schema or config.default_schemas[0]
                _set_statement_timeout(conn, self._settings.statement_timeout_ms)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT column_name, data_type, udt_name, is_nullable, column_default, ordinal_position
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position
                        """,
                        (resolved_schema, table_name),
                    )
                    columns = cur.fetchall()
                    if not columns:
                        raise QueryExecutionError(
                            f"未找到表 {resolved_schema}.{table_name}，或当前用户没有访问权限"
                        )

                    cur.execute(
                        """
                        SELECT kcu.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                          ON tc.constraint_name = kcu.constraint_name
                         AND tc.table_schema = kcu.table_schema
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                          AND tc.table_schema = %s
                          AND tc.table_name = %s
                        ORDER BY kcu.ordinal_position
                        """,
                        (resolved_schema, table_name),
                    )
                    primary_keys = {row["column_name"] for row in cur.fetchall()}

                    cur.execute(
                        """
                        SELECT indexname, indexdef
                        FROM pg_indexes
                        WHERE schemaname = %s AND tablename = %s
                        ORDER BY indexname
                        """,
                        (resolved_schema, table_name),
                    )
                    indexes = cur.fetchall()

                duration_ms = _elapsed_ms(started)
                self._audit.log(
                    tool="describe_table",
                    connection_id=connection_id,
                    success=True,
                    duration_ms=duration_ms,
                    row_count=len(columns),
                    extra={"schema": resolved_schema, "table_name": table_name},
                )
                return {
                    "connection_id": connection_id,
                    "schema": resolved_schema,
                    "table_name": table_name,
                    "columns": [
                        {
                            "column_name": row["column_name"],
                            "data_type": row["data_type"],
                            "udt_name": row["udt_name"],
                            "nullable": row["is_nullable"] == "YES",
                            "default": row["column_default"],
                            "primary_key": row["column_name"] in primary_keys,
                        }
                        for row in columns
                    ],
                    "indexes": indexes,
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
                extra={"schema": schema, "table_name": table_name},
            )
            raise QueryExecutionError(sanitized) from exc

    def _fetch_rows(self, connection_id: str, query: str, params: Optional[List[object]] = None):
        with self._registry.connection(connection_id) as (conn, _):
            _set_statement_timeout(conn, self._settings.statement_timeout_ms)
            with conn.cursor() as cur:
                cur.execute(query, params or [])
                return cur.fetchall()


def _set_statement_timeout(conn, timeout_ms: int) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('statement_timeout', %s, false)", (str(timeout_ms),))


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
