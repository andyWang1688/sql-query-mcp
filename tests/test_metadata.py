from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from sql_query_mcp.audit import AuditLogger
from sql_query_mcp.config import ConnectionConfig, ServerSettings
from sql_query_mcp.errors import QueryExecutionError
from sql_query_mcp.introspection import MetadataService


class _AdapterStub:
    def __init__(self) -> None:
        self.list_tables_calls = []
        self.describe_table_calls = []
        self.set_statement_timeout_calls = []

    def set_statement_timeout(self, conn: object, timeout_ms: int) -> None:
        self.set_statement_timeout_calls.append(timeout_ms)

    def list_schemas(self, conn: object):
        return ["public"]

    def list_databases(self, conn: object):
        return ["crm"]

    def list_tables(self, conn: object, namespace: str):
        self.list_tables_calls.append(namespace)
        return []

    def describe_table(self, conn: object, namespace: str, table_name: str):
        self.describe_table_calls.append((namespace, table_name))
        return {"columns": [{"column_name": "id"}], "indexes": []}


class _RegistryStub:
    def __init__(self, config: ConnectionConfig, adapter: object) -> None:
        self._config = config
        self._adapter = adapter
        self.connection_calls = 0

    def get_connection_config(self, connection_id: str) -> ConnectionConfig:
        if connection_id != self._config.connection_id:
            raise AssertionError(connection_id)
        return self._config

    @contextmanager
    def connection_from_config(self, config: ConnectionConfig):
        if config != self._config:
            raise AssertionError(config)
        self.connection_calls += 1
        yield object(), self._adapter


class MetadataServiceTestCase(unittest.TestCase):
    def test_list_tables_skips_statement_timeout_when_unset(self) -> None:
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
        adapter = _AdapterStub()
        registry = _RegistryStub(config, adapter)
        with tempfile.TemporaryDirectory() as temp_dir:
            service = MetadataService(
                registry=registry,
                settings=ServerSettings(
                    statement_timeout_ms=None,
                    audit_log_path=Path(temp_dir) / "audit.jsonl",
                ),
                audit_logger=AuditLogger(Path(temp_dir) / "audit.jsonl"),
            )
            result = service.list_tables(config.connection_id)

        self.assertEqual([], adapter.set_statement_timeout_calls)
        self.assertEqual("public", result["schema"])

    def test_list_tables_sets_statement_timeout_when_configured(self) -> None:
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
        adapter = _AdapterStub()
        registry = _RegistryStub(config, adapter)
        with tempfile.TemporaryDirectory() as temp_dir:
            service = MetadataService(
                registry=registry,
                settings=ServerSettings(
                    statement_timeout_ms=2500,
                    audit_log_path=Path(temp_dir) / "audit.jsonl",
                ),
                audit_logger=AuditLogger(Path(temp_dir) / "audit.jsonl"),
            )
            service.list_tables(config.connection_id)

        self.assertEqual([2500], adapter.set_statement_timeout_calls)

    def test_list_schemas_rejects_mysql_connections(self) -> None:
        config = ConnectionConfig(
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
            service = MetadataService(
                registry=_RegistryStub(config, _AdapterStub()),
                settings=ServerSettings(audit_log_path=Path(temp_dir) / "audit.jsonl"),
                audit_logger=AuditLogger(Path(temp_dir) / "audit.jsonl"),
            )
            with self.assertRaises(QueryExecutionError):
                service.list_schemas(config.connection_id)
            self.assertEqual(0, service._registry.connection_calls)

    def test_list_databases_rejects_postgres_connections(self) -> None:
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
        with tempfile.TemporaryDirectory() as temp_dir:
            service = MetadataService(
                registry=_RegistryStub(config, _AdapterStub()),
                settings=ServerSettings(audit_log_path=Path(temp_dir) / "audit.jsonl"),
                audit_logger=AuditLogger(Path(temp_dir) / "audit.jsonl"),
            )
            with self.assertRaises(QueryExecutionError):
                service.list_databases(config.connection_id)
            self.assertEqual(0, service._registry.connection_calls)

    def test_list_tables_rejects_invalid_namespace_before_connecting(self) -> None:
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
        registry = _RegistryStub(config, _AdapterStub())
        with tempfile.TemporaryDirectory() as temp_dir:
            service = MetadataService(
                registry=registry,
                settings=ServerSettings(audit_log_path=Path(temp_dir) / "audit.jsonl"),
                audit_logger=AuditLogger(Path(temp_dir) / "audit.jsonl"),
            )
            with self.assertRaises(QueryExecutionError):
                service.list_tables(config.connection_id, database="crm")
        self.assertEqual(0, registry.connection_calls)

    def test_success_audit_contains_engine_for_engine_specific_tools(self) -> None:
        postgres_config = ConnectionConfig(
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
        mysql_config = ConnectionConfig(
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
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "audit.jsonl"
            postgres_service = MetadataService(
                registry=_RegistryStub(postgres_config, _AdapterStub()),
                settings=ServerSettings(audit_log_path=log_path),
                audit_logger=AuditLogger(log_path),
            )
            mysql_service = MetadataService(
                registry=_RegistryStub(mysql_config, _AdapterStub()),
                settings=ServerSettings(audit_log_path=log_path),
                audit_logger=AuditLogger(log_path),
            )

            postgres_service.list_schemas(postgres_config.connection_id)
            mysql_service.list_databases(mysql_config.connection_id)

            records = [
                json.loads(line)
                for line in log_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual("postgres", records[0]["extra"]["engine"])
        self.assertEqual("mysql", records[1]["extra"]["engine"])


if __name__ == "__main__":
    unittest.main()
