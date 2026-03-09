from __future__ import annotations

import unittest

from postgres_query_mcp.errors import SecurityError
from postgres_query_mcp.validator import (
    build_explain_query,
    build_limited_query,
    clamp_limit,
    validate_select_sql,
)


class ValidatorTestCase(unittest.TestCase):
    def test_accepts_plain_select(self) -> None:
        self.assertEqual("SELECT 1", validate_select_sql("SELECT 1;"))

    def test_accepts_cte_select(self) -> None:
        sql = "WITH recent AS (SELECT 1 AS id) SELECT * FROM recent"
        self.assertEqual(sql, validate_select_sql(sql))

    def test_rejects_mutating_keywords(self) -> None:
        with self.assertRaises(SecurityError):
            validate_select_sql("DELETE FROM users")

    def test_rejects_sql_comments(self) -> None:
        with self.assertRaises(SecurityError):
            validate_select_sql("SELECT 1 -- hidden")

    def test_limit_is_clamped(self) -> None:
        self.assertEqual(1000, clamp_limit(5000, 200, 1000))

    def test_build_limited_query_wraps_sql(self) -> None:
        query, sentinel_limit = build_limited_query("SELECT * FROM users", 200)
        self.assertIn("SELECT * FROM (SELECT * FROM users)", query)
        self.assertEqual(201, sentinel_limit)

    def test_build_explain_query_uses_format_json(self) -> None:
        explain_sql = build_explain_query("SELECT 1", analyze=False)
        self.assertIn("FORMAT JSON", explain_sql)
        self.assertIn("ANALYZE FALSE", explain_sql)


if __name__ == "__main__":
    unittest.main()
