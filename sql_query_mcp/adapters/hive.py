"""Hive adapter."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, List
from urllib.parse import parse_qs, unquote, urlparse

try:
    from pyhive import hive
except ImportError:  # pragma: no cover - runtime dependency
    hive = None

from ..errors import ConfigurationError


class HiveAdapter:
    engine = "hive"

    @contextmanager
    def connection(self, connection_id: str, dsn: str) -> Iterator[object]:
        if hive is None:
            raise ConfigurationError("缺少 PyHive 依赖，请先安装项目依赖。")

        conn = hive.Connection(**self._parse_dsn(dsn))
        try:
            yield conn
        finally:
            conn.close()

    def close(self) -> None:
        return None

    def set_statement_timeout(self, conn: object, timeout_ms: int) -> None:
        return None

    def build_sample_query(self, database: str, table_name: str, sentinel_limit: int) -> str:
        return f"SELECT * FROM {self._qualified_table(database, table_name)} LIMIT {int(sentinel_limit)}"

    def build_insert_query(self, database: str, table_name: str, columns: List[str]) -> str:
        quoted_columns = ", ".join(self._quote_identifier(column) for column in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        return f"INSERT INTO {self._qualified_table(database, table_name)} ({quoted_columns}) VALUES ({placeholders})"

    def build_explain_query(self, sql_text: str, analyze: bool = False) -> str:
        prefix = "EXPLAIN ANALYZE" if analyze else "EXPLAIN"
        return f"{prefix} {sql_text}"

    def extract_plan(self, rows):
        return [self._first_value(row) for row in rows]

    def column_names(self, description) -> List[str]:
        return [column[0] for column in (description or [])]

    def normalize_rows(self, rows, columns: List[str]) -> List[dict]:
        return [dict(zip(columns, row)) for row in rows]

    def list_databases(self, conn: object) -> List[str]:
        with conn.cursor() as cur:
            cur.execute("SHOW DATABASES")
            return [self._first_value(row) for row in cur.fetchall()]

    def list_tables(self, conn: object, database: str):
        with conn.cursor() as cur:
            cur.execute(f"SHOW TABLES IN {self._quote_identifier(database)}")
            return [
                {
                    "database_name": database,
                    "table_name": self._first_value(row),
                    "table_type": None,
                }
                for row in cur.fetchall()
            ]

    def describe_table(self, conn: object, database: str, table_name: str):
        with conn.cursor() as cur:
            cur.execute(f"DESCRIBE {self._qualified_table(database, table_name)}")
            rows = cur.fetchall()

        columns = []
        in_partitions = False
        for row in rows:
            name = self._first_value(row)
            if not name:
                continue
            if str(name).startswith("# Partition Information"):
                in_partitions = True
                continue
            if str(name).startswith("#"):
                continue
            values = self._row_values(row)
            data_type = values[1] if len(values) > 1 else None
            comment = values[2] if len(values) > 2 else None
            columns.append(
                {
                    "column_name": name,
                    "data_type": data_type,
                    "udt_name": None,
                    "nullable": True,
                    "default": None,
                    "primary_key": False,
                    "extra": comment,
                    "partition_key": in_partitions,
                }
            )

        if not columns:
            return None
        return {"columns": columns, "indexes": []}

    def _parse_dsn(self, dsn: str) -> dict:
        parsed = urlparse(dsn)
        if parsed.scheme not in {"hive", "hive+pyhive"}:
            raise ConfigurationError(f"Hive DSN 必须使用 hive:// 或 hive+pyhive://，当前为 {parsed.scheme}")

        supported_query_keys = {"auth", "kerberos_service_name", "password"}
        query_params = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        unsupported = sorted(set(query_params) - supported_query_keys)
        if unsupported:
            raise ConfigurationError(f"Hive DSN 包含暂不支持的参数: {unsupported}")

        connect_args = {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 10000,
            "username": unquote(parsed.username) if parsed.username else None,
            "password": unquote(parsed.password) if parsed.password else query_params.get("password"),
            "database": parsed.path.lstrip("/") or None,
            "auth": query_params.get("auth"),
            "kerberos_service_name": query_params.get("kerberos_service_name"),
        }
        return {key: value for key, value in connect_args.items() if value is not None}

    def _quote_identifier(self, value: str) -> str:
        return "`" + value.replace("`", "``") + "`"

    def _qualified_table(self, database: str, table_name: str) -> str:
        return f"{self._quote_identifier(database)}.{self._quote_identifier(table_name)}"

    def _first_value(self, row):
        if isinstance(row, dict):
            return next(iter(row.values()))
        return row[0]

    def _row_values(self, row):
        if isinstance(row, dict):
            return list(row.values())
        return list(row)
