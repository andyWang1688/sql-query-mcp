from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from sql_query_mcp.audit import AuditLogger
from sql_query_mcp.config import ConnectionConfig, ServerSettings
from sql_query_mcp.errors import QueryExecutionError
from sql_query_mcp.executor import QueryExecutor


class _ExplodingAdapter:
    def build_explain_query(self, sql_text: str, analyze: bool = False) -> str:
        raise RuntimeError("adapter exploded")


class _RegistryStub:
    def __init__(self, config: ConnectionConfig, adapter: object) -> None:
        self._config = config
        self._adapter = adapter

    def get_connection_config(self, connection_id: str) -> ConnectionConfig:
        if connection_id != self._config.connection_id:
            raise AssertionError(connection_id)
        return self._config

    def get_adapter(self, config: ConnectionConfig) -> object:
        if config != self._config:
            raise AssertionError(config)
        return self._adapter

    @contextmanager
    def connection_from_config(self, config: ConnectionConfig):
        if config != self._config:
            raise AssertionError(config)
        yield object(), self._adapter


class AuditLoggingTestCase(unittest.TestCase):
    def test_failure_audit_keeps_engine(self) -> None:
        connection = ConnectionConfig(
            connection_id="crm_prod_main_ro",
            engine="mysql",
            label="CRM MySQL",
            env="prod",
            tenant="main",
            role="ro",
            dsn_env="MYSQL_CONN",
            enabled=True,
            default_database="crm",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "audit.jsonl"
            executor = QueryExecutor(
                registry=_RegistryStub(connection, _ExplodingAdapter()),
                settings=ServerSettings(audit_log_path=log_path),
                audit_logger=AuditLogger(log_path),
            )

            with self.assertRaises(QueryExecutionError):
                executor.explain_query(connection.connection_id, "SELECT 1")

            records = [
                json.loads(line)
                for line in log_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(1, len(records))
        self.assertFalse(records[0]["success"])
        self.assertEqual("explain_query", records[0]["tool"])
        self.assertEqual("mysql", records[0]["extra"]["engine"])


if __name__ == "__main__":
    unittest.main()
