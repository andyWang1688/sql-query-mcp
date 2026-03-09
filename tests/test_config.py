from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from postgres_query_mcp.config import DEFAULT_CONFIG_PATH, load_config
from postgres_query_mcp.errors import ConfigurationError


class ConfigTestCase(unittest.TestCase):
    def test_missing_config_uses_empty_defaults(self) -> None:
        config = load_config("/tmp/does-not-exist-postgres-query-mcp.json")
        self.assertEqual([], config.connections)
        self.assertGreater(config.settings.default_limit, 0)

    def test_valid_config_loads_connections(self) -> None:
        payload = {
            "settings": {"default_limit": 100, "max_limit": 500},
            "connections": [
                {
                    "connection_id": "crm_prod_muqiao_ro",
                    "label": "CRM Prod",
                    "env": "prod",
                    "tenant": "muqiao",
                    "role": "ro",
                    "dsn_env": "PG_CONN_CRM_PROD_MUQIAO_RO",
                    "enabled": True,
                    "default_schemas": ["public"],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "connections.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            config = load_config(str(path))

        self.assertEqual(1, len(config.connections))
        self.assertEqual("crm_prod_muqiao_ro", config.connections[0].connection_id)
        self.assertEqual(100, config.settings.default_limit)
        self.assertEqual(500, config.settings.max_limit)

    def test_duplicate_connection_ids_fail(self) -> None:
        payload = {
            "connections": [
                {
                    "connection_id": "crm_prod_muqiao_ro",
                    "env": "prod",
                    "tenant": "muqiao",
                    "role": "ro",
                    "dsn_env": "PG_CONN_A",
                },
                {
                    "connection_id": "crm_prod_muqiao_ro",
                    "env": "uat",
                    "tenant": "muqiao",
                    "role": "ro",
                    "dsn_env": "PG_CONN_B",
                },
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "connections.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_config(str(path))


if __name__ == "__main__":
    unittest.main()
