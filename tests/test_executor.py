from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from sql_query_mcp.adapters.mysql import MySQLAdapter
from sql_query_mcp.audit import AuditLogger
from sql_query_mcp.config import ConnectionConfig, ServerSettings
from sql_query_mcp.errors import QueryExecutionError
from sql_query_mcp.executor import QueryExecutor


class _SampleAdapter:
    def build_sample_query(self, namespace: str, table_name: str, sentinel_limit: int) -> str:
        return f"SELECT * FROM {namespace}.{table_name} LIMIT {sentinel_limit}"


class _RegistryStub:
    def __init__(self, config: ConnectionConfig, adapter: object) -> None:
        self._config = config
        self._adapter = adapter
        self.connection_calls = 0

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
        self.connection_calls += 1
        yield object(), self._adapter


class QueryExecutorValidationTestCase(unittest.TestCase):
    def test_mysql_explain_rejects_analyze_before_connecting(self) -> None:
        config = ConnectionConfig(
            connection_id="crm_mysql_prod_main_ro",
            engine="mysql",
            label="CRM MySQL",
            env="prod",
            tenant="main",
            role="ro",
            dsn_env="MYSQL_CONN",
            enabled=True,
            default_database="crm",
        )
        registry = _RegistryStub(config, MySQLAdapter())
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = QueryExecutor(
                registry=registry,
                settings=ServerSettings(audit_log_path=Path(temp_dir) / "audit.jsonl"),
                audit_logger=AuditLogger(Path(temp_dir) / "audit.jsonl"),
            )
            with self.assertRaises(QueryExecutionError):
                executor.explain_query(config.connection_id, "SELECT 1", analyze=True)
        self.assertEqual(0, registry.connection_calls)

    def test_get_table_sample_rejects_invalid_namespace_before_connecting(self) -> None:
        config = ConnectionConfig(
            connection_id="crm_prod_main_ro",
            engine="postgres",
            label="CRM PG",
            env="prod",
            tenant="main",
            role="ro",
            dsn_env="PG_CONN",
            enabled=True,
            default_schema="public",
        )
        registry = _RegistryStub(config, _SampleAdapter())
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = QueryExecutor(
                registry=registry,
                settings=ServerSettings(audit_log_path=Path(temp_dir) / "audit.jsonl"),
                audit_logger=AuditLogger(Path(temp_dir) / "audit.jsonl"),
            )
            with self.assertRaises(QueryExecutionError):
                executor.get_table_sample(config.connection_id, "orders", database="crm")
        self.assertEqual(0, registry.connection_calls)


if __name__ == "__main__":
    unittest.main()
