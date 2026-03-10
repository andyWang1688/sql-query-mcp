from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sql_query_mcp.config import load_config
from sql_query_mcp.errors import ConfigurationError


class ConfigTestCase(unittest.TestCase):
    def test_missing_config_uses_empty_defaults(self) -> None:
        config = load_config("/tmp/does-not-exist-sql-query-mcp.json")
        self.assertEqual([], config.connections)
        self.assertGreater(config.settings.default_limit, 0)

    def test_valid_config_loads_connections(self) -> None:
        payload = {
            "settings": {"default_limit": 100, "max_limit": 500},
            "connections": [
                {
                    "connection_id": "crm_prod_muqiao_ro",
                    "engine": "postgres",
                    "label": "CRM Prod",
                    "env": "prod",
                    "tenant": "muqiao",
                    "role": "ro",
                    "dsn_env": "PG_CONN_CRM_PROD_MUQIAO_RO",
                    "enabled": True,
                    "default_schema": "public",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "connections.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            config = load_config(str(path))

        self.assertEqual(1, len(config.connections))
        self.assertEqual("crm_prod_muqiao_ro", config.connections[0].connection_id)
        self.assertEqual("postgres", config.connections[0].engine)
        self.assertEqual(100, config.settings.default_limit)
        self.assertEqual(500, config.settings.max_limit)

    def test_missing_engine_fails(self) -> None:
        payload = {
            "connections": [
                {
                    "connection_id": "crm_prod_muqiao_ro",
                    "label": "CRM Prod",
                    "env": "prod",
                    "tenant": "muqiao",
                    "role": "ro",
                    "dsn_env": "PG_CONN_A",
                    "enabled": True,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "connections.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_config(str(path))

    def test_postgres_cannot_define_default_database(self) -> None:
        payload = {
            "connections": [
                {
                    "connection_id": "crm_prod_muqiao_ro",
                    "engine": "postgres",
                    "label": "CRM Prod",
                    "env": "prod",
                    "tenant": "muqiao",
                    "role": "ro",
                    "dsn_env": "PG_CONN_A",
                    "default_database": "crm",
                    "enabled": True,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "connections.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_config(str(path))

    def test_mysql_cannot_define_default_schema(self) -> None:
        payload = {
            "connections": [
                {
                    "connection_id": "crm_prod_muqiao_ro",
                    "engine": "mysql",
                    "label": "CRM MySQL Prod",
                    "env": "prod",
                    "tenant": "muqiao",
                    "role": "ro",
                    "dsn_env": "MYSQL_CONN_A",
                    "default_schema": "public",
                    "enabled": True,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "connections.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_config(str(path))

    def test_duplicate_connection_ids_fail(self) -> None:
        payload = {
            "connections": [
                {
                    "connection_id": "crm_prod_muqiao_ro",
                    "engine": "postgres",
                    "label": "CRM Prod",
                    "env": "prod",
                    "tenant": "muqiao",
                    "role": "ro",
                    "dsn_env": "PG_CONN_A",
                    "enabled": True,
                },
                {
                    "connection_id": "crm_prod_muqiao_ro",
                    "engine": "mysql",
                    "label": "CRM MySQL UAT",
                    "env": "uat",
                    "tenant": "muqiao",
                    "role": "ro",
                    "dsn_env": "PG_CONN_B",
                    "enabled": True,
                },
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "connections.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_config(str(path))

    def test_missing_label_fails(self) -> None:
        payload = {
            "connections": [
                {
                    "connection_id": "crm_prod_muqiao_ro",
                    "engine": "postgres",
                    "env": "prod",
                    "tenant": "muqiao",
                    "role": "ro",
                    "dsn_env": "PG_CONN_A",
                    "enabled": True,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "connections.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_config(str(path))

    def test_missing_enabled_fails(self) -> None:
        payload = {
            "connections": [
                {
                    "connection_id": "crm_prod_muqiao_ro",
                    "engine": "postgres",
                    "label": "CRM Prod",
                    "env": "prod",
                    "tenant": "muqiao",
                    "role": "ro",
                    "dsn_env": "PG_CONN_A",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "connections.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_config(str(path))

    def test_enabled_must_be_bool(self) -> None:
        payload = {
            "connections": [
                {
                    "connection_id": "crm_prod_muqiao_ro",
                    "engine": "postgres",
                    "label": "CRM Prod",
                    "env": "prod",
                    "tenant": "muqiao",
                    "role": "ro",
                    "dsn_env": "PG_CONN_A",
                    "enabled": "true",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "connections.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_config(str(path))

    def test_legacy_default_schemas_fails(self) -> None:
        payload = {
            "connections": [
                {
                    "connection_id": "crm_prod_muqiao_ro",
                    "engine": "postgres",
                    "label": "CRM Prod",
                    "env": "prod",
                    "tenant": "muqiao",
                    "role": "ro",
                    "dsn_env": "PG_CONN_A",
                    "enabled": True,
                    "default_schemas": ["public"],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "connections.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_config(str(path))

    def test_legacy_default_namespace_fails(self) -> None:
        payload = {
            "connections": [
                {
                    "connection_id": "crm_prod_muqiao_ro",
                    "engine": "mysql",
                    "label": "CRM MySQL Prod",
                    "env": "prod",
                    "tenant": "muqiao",
                    "role": "ro",
                    "dsn_env": "MYSQL_CONN_A",
                    "enabled": True,
                    "default_namespace": "crm",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "connections.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_config(str(path))

    def test_audit_log_path_is_relative_to_config_file(self) -> None:
        payload = {
            "settings": {"audit_log_path": "logs/custom-audit.jsonl"},
            "connections": [
                {
                    "connection_id": "crm_prod_muqiao_ro",
                    "engine": "postgres",
                    "label": "CRM Prod",
                    "env": "prod",
                    "tenant": "muqiao",
                    "role": "ro",
                    "dsn_env": "PG_CONN_A",
                    "enabled": True,
                    "default_schema": "public",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "nested"
            config_dir.mkdir()
            path = config_dir / "connections.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            config = load_config(str(path))

        self.assertEqual(
            (config_dir / "logs" / "custom-audit.jsonl").resolve(),
            config.settings.audit_log_path,
        )


if __name__ == "__main__":
    unittest.main()
