"""MySQL adapter."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Iterator, List
from urllib.parse import parse_qs, unquote, urlparse

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:  # pragma: no cover - runtime dependency
    pymysql = None
    DictCursor = None

from ..errors import ConfigurationError, SecurityError


class MySQLAdapter:
    engine = "mysql"

    @contextmanager
    def connection(self, connection_id: str, dsn: str) -> Iterator[object]:
        if pymysql is None or DictCursor is None:
            raise ConfigurationError("缺少 PyMySQL 依赖，请先安装项目依赖。")

        conn = pymysql.connect(
            autocommit=True,
            cursorclass=DictCursor,
            **self._parse_dsn(dsn),
        )
        try:
            yield conn
        finally:
            conn.close()

    def close(self) -> None:
        return None

    def set_statement_timeout(self, conn: object, timeout_ms: int) -> None:
        with conn.cursor() as cur:
            cur.execute("SET SESSION max_execution_time = %s", (int(timeout_ms),))

    def list_databases(self, conn: object) -> List[str]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT schema_name AS database_name
                FROM information_schema.schemata
                WHERE schema_name NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
                ORDER BY schema_name
                """
            )
            return [row["database_name"] for row in cur.fetchall()]

    def list_tables(self, conn: object, database: str):
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_schema AS database_name, table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = %s
                ORDER BY table_name
                """,
                (database,),
            )
            return cur.fetchall()

    def describe_table(self, conn: object, database: str, table_name: str):
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name, column_type, is_nullable, column_default, extra, column_key, ordinal_position
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (database, table_name),
            )
            columns = cur.fetchall()
            cur.execute(
                """
                SELECT index_name, non_unique, seq_in_index, column_name
                FROM information_schema.statistics
                WHERE table_schema = %s AND table_name = %s
                ORDER BY index_name, seq_in_index
                """,
                (database, table_name),
            )
            index_rows = cur.fetchall()

        if not columns:
            return None

        return {
            "columns": [
                {
                    "column_name": row["column_name"],
                    "data_type": row["column_type"],
                    "udt_name": None,
                    "nullable": row["is_nullable"] == "YES",
                    "default": row["column_default"],
                    "primary_key": row["column_key"] == "PRI",
                    "extra": row["extra"],
                }
                for row in columns
            ],
            "indexes": self._normalize_indexes(index_rows),
        }

    def build_sample_query(self, database: str, table_name: str, sentinel_limit: int) -> str:
        return (
            f"SELECT * FROM {self._quote_identifier(database)}."
            f"{self._quote_identifier(table_name)} LIMIT {int(sentinel_limit)}"
        )

    def build_explain_query(self, sql_text: str, analyze: bool = False) -> str:
        if analyze:
            raise SecurityError("MySQL 首版不支持 analyze=True。")
        return f"EXPLAIN FORMAT=JSON {sql_text}"

    def extract_plan(self, rows):
        if not rows:
            return []
        plan = rows[0].get("EXPLAIN", [])
        if isinstance(plan, str):
            try:
                return json.loads(plan)
            except json.JSONDecodeError:
                return plan
        return plan

    def column_names(self, description) -> List[str]:
        return [column[0] for column in (description or [])]

    def _parse_dsn(self, dsn: str) -> dict:
        parsed = urlparse(dsn)
        if parsed.scheme not in {"mysql", "mysql+pymysql"}:
            raise ConfigurationError(f"MySQL DSN 必须使用 mysql:// 或 mysql+pymysql://，当前为 {parsed.scheme}")

        query_params = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        connect_args = {
            "host": parsed.hostname or "localhost",
            "user": unquote(parsed.username) if parsed.username else None,
            "password": unquote(parsed.password) if parsed.password else None,
            "port": parsed.port or 3306,
            "database": parsed.path.lstrip("/") or None,
            "charset": query_params.get("charset", "utf8mb4"),
        }
        return {key: value for key, value in connect_args.items() if value is not None}

    def _quote_identifier(self, value: str) -> str:
        return "`" + value.replace("`", "``") + "`"

    def _normalize_indexes(self, rows: List[dict]) -> List[dict]:
        grouped = {}
        for row in rows:
            index_name = row["index_name"]
            item = grouped.setdefault(
                index_name,
                {
                    "index_name": index_name,
                    "columns": [],
                    "unique": row["non_unique"] == 0,
                    "primary_key": index_name == "PRIMARY",
                    "definition": None,
                },
            )
            item["columns"].append(row["column_name"])
        return [grouped[name] for name in sorted(grouped)]
