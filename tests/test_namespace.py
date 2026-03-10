from __future__ import annotations

import unittest

from sql_query_mcp.config import ConnectionConfig
from sql_query_mcp.errors import SecurityError
from sql_query_mcp.namespace import resolve_namespace


class NamespaceResolutionTestCase(unittest.TestCase):
    def test_postgres_uses_schema_argument(self) -> None:
        config = ConnectionConfig(
            connection_id="crm_prod_main_ro",
            engine="postgres",
            env="prod",
            tenant="main",
            role="ro",
            dsn_env="PG_CONN",
            default_schema="public",
        )
        namespace = resolve_namespace(config, schema="analytics")
        self.assertEqual("schema", namespace.field_name)
        self.assertEqual("analytics", namespace.value)

    def test_postgres_falls_back_to_default_schema(self) -> None:
        config = ConnectionConfig(
            connection_id="crm_prod_main_ro",
            engine="postgres",
            env="prod",
            tenant="main",
            role="ro",
            dsn_env="PG_CONN",
            default_schema="public",
        )
        namespace = resolve_namespace(config)
        self.assertEqual("public", namespace.value)

    def test_mysql_rejects_schema_argument(self) -> None:
        config = ConnectionConfig(
            connection_id="crm_mysql_prod_main_ro",
            engine="mysql",
            env="prod",
            tenant="main",
            role="ro",
            dsn_env="MYSQL_CONN",
            default_database="crm",
        )
        with self.assertRaises(SecurityError):
            resolve_namespace(config, schema="public")

    def test_mysql_falls_back_to_default_database(self) -> None:
        config = ConnectionConfig(
            connection_id="crm_mysql_prod_main_ro",
            engine="mysql",
            env="prod",
            tenant="main",
            role="ro",
            dsn_env="MYSQL_CONN",
            default_database="crm",
        )
        namespace = resolve_namespace(config)
        self.assertEqual("database", namespace.field_name)
        self.assertEqual("crm", namespace.value)

    def test_schema_and_database_cannot_both_be_set(self) -> None:
        config = ConnectionConfig(
            connection_id="crm_prod_main_ro",
            engine="postgres",
            env="prod",
            tenant="main",
            role="ro",
            dsn_env="PG_CONN",
            default_schema="public",
        )
        with self.assertRaises(SecurityError):
            resolve_namespace(config, schema="public", database="crm")


if __name__ == "__main__":
    unittest.main()
