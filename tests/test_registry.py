from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from sql_query_mcp.config import AppConfig, ConnectionConfig, ServerSettings
from sql_query_mcp.registry import ConnectionRegistry


class _FakeAdapter:
    def __init__(self, engine: str) -> None:
        self.engine = engine
        self.calls = []

    @contextmanager
    def connection(self, connection_id: str, dsn: str):
        self.calls.append((connection_id, dsn))
        yield {"connection_id": connection_id, "dsn": dsn}

    def close(self) -> None:
        return None


class RegistryRoutingTestCase(unittest.TestCase):
    def test_routes_only_by_configured_engine(self) -> None:
        postgres_config = ConnectionConfig(
            connection_id="tenant_mysql_hint_prod_ro",
            engine="postgres",
            label="PG",
            env="prod",
            tenant="main",
            role="ro",
            dsn_env="PG_DSN",
            enabled=True,
            default_schema="public",
        )
        mysql_config = ConnectionConfig(
            connection_id="tenant_pg_hint_prod_ro",
            engine="mysql",
            label="MySQL",
            env="prod",
            tenant="main",
            role="ro",
            dsn_env="MYSQL_DSN",
            enabled=True,
            default_database="crm",
        )
        registry = ConnectionRegistry(
            AppConfig(settings=ServerSettings(), connections=[postgres_config, mysql_config])
        )
        fake_postgres = _FakeAdapter("postgres")
        fake_mysql = _FakeAdapter("mysql")
        registry._adapters = {
            "postgres": fake_postgres,
            "mysql": fake_mysql,
        }

        with patch.dict(
            os.environ,
            {"PG_DSN": "postgresql://pg", "MYSQL_DSN": "mysql://mysql"},
            clear=False,
        ):
            with registry.connection("tenant_mysql_hint_prod_ro") as (_, config, adapter):
                self.assertEqual("postgres", config.engine)
                self.assertIs(adapter, fake_postgres)

            with registry.connection("tenant_pg_hint_prod_ro") as (_, config, adapter):
                self.assertEqual("mysql", config.engine)
                self.assertIs(adapter, fake_mysql)

        self.assertEqual([("tenant_mysql_hint_prod_ro", "postgresql://pg")], fake_postgres.calls)
        self.assertEqual([("tenant_pg_hint_prod_ro", "mysql://mysql")], fake_mysql.calls)


if __name__ == "__main__":
    unittest.main()
