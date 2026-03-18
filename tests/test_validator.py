from __future__ import annotations

import json
import unittest

from sql_query_mcp.validator import (
    build_limited_query,
    clamp_limit,
    validate_select_sql,
)
from sql_query_mcp.adapters.mysql import MySQLAdapter
from sql_query_mcp.adapters.postgres import PostgresAdapter
from sql_query_mcp.errors import SecurityError


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

    def test_mysql_explain_plan_is_parsed_to_structured_json(self) -> None:
        plan = MySQLAdapter().extract_plan(
            [{"EXPLAIN": json.dumps({"query_block": {"select_id": 1}})}]
        )
        self.assertEqual({"query_block": {"select_id": 1}}, plan)

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
