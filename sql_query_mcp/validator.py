"""SQL validation and normalization."""

from __future__ import annotations

import re
from typing import Optional, Tuple

from .errors import SecurityError

COMMENT_TOKENS = ("--", "/*", "*/")
BANNED_KEYWORDS_RE = re.compile(
    r"\b(insert|update|delete|alter|drop|truncate|copy|create|grant|revoke|comment|refresh|merge|call|vacuum|set|reset|do)\b",
    re.IGNORECASE,
)


def validate_select_sql(sql: str) -> str:
    cleaned = _clean_sql(sql)
    lowered = cleaned.lstrip().lower()
    if lowered.startswith("explain"):
        raise SecurityError("explain_query 会自动包装 SQL，请直接传 SELECT 或 WITH 查询。")
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise SecurityError("仅允许 SELECT 或 WITH ... SELECT 语句。")
    _reject_banned_keywords(cleaned)
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


def _reject_banned_keywords(sql: str) -> None:
    match = BANNED_KEYWORDS_RE.search(sql)
    if match:
        raise SecurityError(f"检测到禁止关键字: {match.group(1)}")
