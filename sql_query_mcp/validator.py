"""SQL validation and normalization."""

from __future__ import annotations

import re
from typing import Any, Optional, Tuple

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from .errors import SecurityError

COMMENT_TOKENS = ("--", "/*", "*/")
READ_ONLY_ROOT_TYPES = tuple(
    expr_type
    for expr_type in (
        getattr(exp, name, None) for name in ("Select", "Union", "Except", "Intersect")
    )
    if isinstance(expr_type, type)
)
MUTATING_EXPRESSION_TYPES = tuple(
    expr_type
    for expr_type in (
        getattr(exp, name, None)
        for name in (
            "Insert",
            "Update",
            "Delete",
            "Merge",
            "Create",
            "Drop",
            "Alter",
            "Command",
            "Copy",
            "Call",
            "Set",
            "Pragma",
            "Use",
            "Grant",
            "Revoke",
            "Transaction",
            "Commit",
            "Rollback",
            "TruncateTable",
            "Vacuum",
            "Into",
        )
    )
    if isinstance(expr_type, type)
)
DIALECT_BY_ENGINE = {"postgres": "postgres", "mysql": "mysql"}


def validate_select_sql(sql: str, engine: str) -> str:
    cleaned = _clean_sql(sql)
    lowered = cleaned.lstrip().lower()
    if lowered.startswith("explain"):
        raise SecurityError(
            "explain_query 会自动包装 SQL，请直接传 SELECT 或 WITH 查询。"
        )
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise SecurityError("仅允许 SELECT 或 WITH ... SELECT 语句。")
    statement = _parse_statement(cleaned, engine)
    _ensure_read_only_statement(statement)
    return cleaned


def clamp_limit(limit: Optional[int], default_limit: int, max_limit: int) -> int:
    value = default_limit if limit is None else int(limit)
    if value <= 0:
        raise SecurityError("limit 必须大于 0。")
    return min(value, max_limit)


def build_limited_query(sql: str, row_limit: int) -> Tuple[str, int]:
    sentinel_limit = row_limit + 1
    wrapped = f"SELECT * FROM ({sql}) AS _pq_result LIMIT {sentinel_limit}"
    return wrapped, sentinel_limit


def summarize_sql(sql: str, max_chars: int = 160) -> str:
    one_line = re.sub(r"\s+", " ", sql).strip()
    if len(one_line) <= max_chars:
        return one_line
    return one_line[: max_chars - 3] + "..."


def _clean_sql(sql: str) -> str:
    if not sql or not sql.strip():
        raise SecurityError("SQL 不能为空。")

    cleaned = sql.strip()
    for token in COMMENT_TOKENS:
        if token in cleaned:
            raise SecurityError("不允许使用 SQL 注释。")

    semicolon_count = cleaned.count(";")
    if semicolon_count > 1:
        raise SecurityError("只允许单条 SQL 语句。")
    if semicolon_count == 1 and not cleaned.endswith(";"):
        raise SecurityError("只允许单条 SQL 语句。")
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].rstrip()

    if not cleaned:
        raise SecurityError("SQL 不能为空。")
    return cleaned


def _parse_statement(sql: str, engine: str) -> Any:
    try:
        dialect = DIALECT_BY_ENGINE[engine]
    except KeyError as exc:
        raise SecurityError(f"不支持的 SQL 方言: {engine}") from exc

    try:
        return parse_one(sql, dialect=dialect)
    except ParseError as exc:
        raise SecurityError(f"SQL 解析失败，已拒绝执行: {exc}") from exc


def _ensure_read_only_statement(statement: Any) -> None:
    if not isinstance(statement, READ_ONLY_ROOT_TYPES):
        raise SecurityError("仅允许 SELECT 或 WITH ... SELECT 语句。")

    for node in statement.walk():
        if isinstance(node, MUTATING_EXPRESSION_TYPES):
            raise SecurityError(f"仅允许只读查询，检测到写操作: {node.key.upper()}")
