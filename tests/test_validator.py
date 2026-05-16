from __future__ import annotations

import json
import unittest

from sql_query_mcp.validator import (
    build_limited_query,
    clamp_limit,
    validate_select_sql,
)
from sql_query_mcp.adapters.hive import HiveAdapter
from sql_query_mcp.adapters.mysql import MySQLAdapter
from sql_query_mcp.adapters.postgres import PostgresAdapter
from sql_query_mcp.errors import SecurityError


class _HiveCursorStub:
    def __init__(self, rows) -> None:
        self._rows = rows
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str) -> None:
        self.executed.append(sql)

    def fetchall(self):
        return self._rows


class _HiveConnectionStub:
    def __init__(self, rows) -> None:
        self.cursor_stub = _HiveCursorStub(rows)

    def cursor(self) -> _HiveCursorStub:
        return self.cursor_stub


class ValidatorTestCase(unittest.TestCase):
    def test_accepts_plain_select(self) -> None:
        self.assertEqual("SELECT 1", validate_select_sql("SELECT 1;", "postgres"))

    def test_accepts_cte_select(self) -> None:
        sql = "WITH recent AS (SELECT 1 AS id) SELECT * FROM recent"
        self.assertEqual(sql, validate_select_sql(sql, "postgres"))

    def test_allows_string_literal_with_call_prefix(self) -> None:
        sql = "SELECT * FROM users WHERE note ILIKE 'call %'"
        self.assertEqual(sql, validate_select_sql(sql, "postgres"))

    def test_allows_string_literal_with_mutating_keyword(self) -> None:
        sql = "SELECT * FROM users WHERE status = 'delete pending'"
        self.assertEqual(sql, validate_select_sql(sql, "mysql"))

    def test_rejects_delete_statement(self) -> None:
        with self.assertRaises(SecurityError):
            validate_select_sql("DELETE FROM users", "postgres")

    def test_rejects_call_statement(self) -> None:
        with self.assertRaises(SecurityError):
            validate_select_sql("CALL refresh_orders()", "mysql")

    def test_rejects_writable_cte(self) -> None:
        sql = "WITH deleted_rows AS (DELETE FROM users RETURNING id) SELECT * FROM deleted_rows"
        with self.assertRaises(SecurityError):
            validate_select_sql(sql, "postgres")

    def test_rejects_sql_comments(self) -> None:
        with self.assertRaises(SecurityError):
            validate_select_sql("SELECT 1 -- hidden", "postgres")

    def test_limit_is_clamped(self) -> None:
        self.assertEqual(1000, clamp_limit(5000, 200, 1000))

    def test_build_limited_query_wraps_sql(self) -> None:
        query, sentinel_limit = build_limited_query("SELECT * FROM users", 200)
        self.assertIn("SELECT * FROM (SELECT * FROM users)", query)
        self.assertEqual(201, sentinel_limit)

    def test_build_limited_query_uses_hive_compatible_alias(self) -> None:
        query, sentinel_limit = build_limited_query(
            "SELECT * FROM default.students", 5, engine="hive"
        )

        self.assertEqual(
            "SELECT * FROM (SELECT * FROM default.students) _pq_result LIMIT 6",
            query,
        )
        self.assertEqual(6, sentinel_limit)

    def test_postgres_explain_uses_format_json(self) -> None:
        explain_sql = PostgresAdapter().build_explain_query("SELECT 1", analyze=False)
        self.assertIn("FORMAT JSON", explain_sql)
        self.assertIn("ANALYZE FALSE", explain_sql)

    def test_mysql_explain_uses_format_json(self) -> None:
        explain_sql = MySQLAdapter().build_explain_query("SELECT 1", analyze=False)
        self.assertEqual("EXPLAIN FORMAT=JSON SELECT 1", explain_sql)

    def test_mysql_explain_rejects_analyze(self) -> None:
        with self.assertRaises(SecurityError):
            MySQLAdapter().build_explain_query("SELECT 1", analyze=True)

    def test_hive_parse_dsn_uses_hiveserver2_defaults(self) -> None:
        options = HiveAdapter()._parse_dsn(
            "hive://alice:secret@hive.example.com:10000/analytics?auth=CUSTOM"
        )

        self.assertEqual("hive.example.com", options["host"])
        self.assertEqual(10000, options["port"])
        self.assertEqual("alice", options["username"])
        self.assertEqual("secret", options["password"])
        self.assertEqual("analytics", options["database"])
        self.assertEqual("CUSTOM", options["auth"])

    def test_hive_parse_dsn_rejects_unsupported_scheme(self) -> None:
        with self.assertRaises(Exception):
            HiveAdapter()._parse_dsn("mysql://alice:secret@localhost/default")

    def test_hive_parse_dsn_rejects_unsupported_query_keys(self) -> None:
        with self.assertRaises(Exception):
            HiveAdapter()._parse_dsn("hive://localhost/default?configuration=x")

    def test_hive_quotes_identifiers_with_backticks(self) -> None:
        self.assertEqual(
            "`default`.`orders``2026`",
            HiveAdapter()._qualified_table("default", "orders`2026"),
        )

    def test_hive_validator_accepts_select(self) -> None:
        self.assertEqual("SELECT * FROM orders", validate_select_sql("SELECT * FROM orders", "hive"))

    def test_hive_build_sample_query_quotes_identifiers(self) -> None:
        query = HiveAdapter().build_sample_query("analytics", "orders", 201)
        self.assertEqual("SELECT * FROM `analytics`.`orders` LIMIT 201", query)

    def test_hive_build_insert_query_quotes_identifiers(self) -> None:
        query = HiveAdapter().build_insert_query("analytics", "orders", ["order", "status"])

        self.assertEqual(
            "INSERT INTO `analytics`.`orders` (`order`, `status`) VALUES (%s, %s)",
            query,
        )

    def test_hive_explain_uses_text_explain(self) -> None:
        self.assertEqual("EXPLAIN SELECT 1", HiveAdapter().build_explain_query("SELECT 1"))

    def test_hive_explain_analyze_uses_supported_explain_form(self) -> None:
        self.assertEqual(
            "EXPLAIN ANALYZE SELECT 1",
            HiveAdapter().build_explain_query("SELECT 1", analyze=True),
        )

    def test_hive_extract_plan_returns_text_lines(self) -> None:
        plan = HiveAdapter().extract_plan([("Plan line 1",), ("Plan line 2",)])
        self.assertEqual(["Plan line 1", "Plan line 2"], plan)

    def test_hive_column_names_read_dbapi_description(self) -> None:
        self.assertEqual(["id", "name"], HiveAdapter().column_names([("id",), ("name",)]))

    def test_hive_list_databases_uses_show_databases(self) -> None:
        conn = _HiveConnectionStub([("default",), ("analytics",)])

        databases = HiveAdapter().list_databases(conn)

        self.assertEqual(["default", "analytics"], databases)
        self.assertEqual(["SHOW DATABASES"], conn.cursor_stub.executed)

    def test_hive_list_tables_returns_normalized_rows(self) -> None:
        conn = _HiveConnectionStub([("orders",), ("customers",)])

        tables = HiveAdapter().list_tables(conn, "analytics")

        self.assertEqual(
            [
                {"database_name": "analytics", "table_name": "orders", "table_type": None},
                {"database_name": "analytics", "table_name": "customers", "table_type": None},
            ],
            tables,
        )
        self.assertEqual(["SHOW TABLES IN `analytics`"], conn.cursor_stub.executed)

    def test_hive_describe_table_returns_columns_and_empty_indexes(self) -> None:
        conn = _HiveConnectionStub(
            [
                ("id", "int", ""),
                ("name", "string", "customer name"),
                ("", None, None),
                ("# Partition Information", None, None),
                ("# col_name", "data_type", "comment"),
                ("dt", "string", "partition date"),
            ]
        )

        description = HiveAdapter().describe_table(conn, "analytics", "orders")

        self.assertEqual(
            [
                {
                    "column_name": "id",
                    "data_type": "int",
                    "udt_name": None,
                    "nullable": True,
                    "default": None,
                    "primary_key": False,
                    "extra": "",
                    "partition_key": False,
                },
                {
                    "column_name": "name",
                    "data_type": "string",
                    "udt_name": None,
                    "nullable": True,
                    "default": None,
                    "primary_key": False,
                    "extra": "customer name",
                    "partition_key": False,
                },
                {
                    "column_name": "dt",
                    "data_type": "string",
                    "udt_name": None,
                    "nullable": True,
                    "default": None,
                    "primary_key": False,
                    "extra": "partition date",
                    "partition_key": True,
                },
            ],
            description["columns"],
        )
        self.assertEqual([], description["indexes"])

    def test_mysql_explain_plan_is_parsed_to_structured_json(self) -> None:
        plan = MySQLAdapter().extract_plan(
            [{"EXPLAIN": json.dumps({"query_block": {"select_id": 1}})}]
        )
        self.assertEqual({"query_block": {"select_id": 1}}, plan)

    def test_postgres_build_insert_query_quotes_identifiers(self) -> None:
        query = PostgresAdapter().build_insert_query(
            "public", "orders", ["order", "status"]
        )

        self.assertEqual(
            'INSERT INTO "public"."orders" ("order", "status") VALUES (%s, %s)',
            query.as_string(None),
        )

    def test_mysql_build_insert_query_quotes_identifiers(self) -> None:
        query = MySQLAdapter().build_insert_query(
            "crm", "orders", ["order", "status"]
        )

        self.assertEqual(
            "INSERT INTO `crm`.`orders` (`order`, `status`) VALUES (%s, %s)",
            query,
        )

    def test_mysql_indexes_are_normalized(self) -> None:
        indexes = MySQLAdapter()._normalize_indexes(
            [
                {
                    "index_name": "PRIMARY",
                    "non_unique": 0,
                    "seq_in_index": 1,
                    "column_name": "id",
                },
                {
                    "index_name": "idx_orders_status_created_at",
                    "non_unique": 1,
                    "seq_in_index": 1,
                    "column_name": "status",
                },
                {
                    "index_name": "idx_orders_status_created_at",
                    "non_unique": 1,
                    "seq_in_index": 2,
                    "column_name": "created_at",
                },
            ]
        )
        self.assertEqual(
            [
                {
                    "index_name": "PRIMARY",
                    "columns": ["id"],
                    "unique": True,
                    "primary_key": True,
                    "definition": None,
                },
                {
                    "index_name": "idx_orders_status_created_at",
                    "columns": ["status", "created_at"],
                    "unique": False,
                    "primary_key": False,
                    "definition": None,
                },
            ],
            indexes,
        )


if __name__ == "__main__":
    unittest.main()
