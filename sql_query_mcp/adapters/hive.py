"""Hive adapter."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
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

    def _parse_dsn(self, dsn: str) -> dict:
        parsed = urlparse(dsn)
        if parsed.scheme not in {"hive", "hive+pyhive"}:
            raise ConfigurationError(f"Hive DSN 必须使用 hive:// 或 hive+pyhive://，当前为 {parsed.scheme}")

        supported_query_keys = {"auth", "kerberos_service_name", "configuration", "password"}
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
