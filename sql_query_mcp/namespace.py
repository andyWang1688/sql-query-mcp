"""Namespace resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import ConnectionConfig
from .errors import SecurityError


@dataclass(frozen=True)
class NamespaceSelection:
    field_name: str
    value: str


def resolve_namespace(
    config: ConnectionConfig,
    *,
    schema: Optional[str] = None,
    database: Optional[str] = None,
) -> NamespaceSelection:
    if schema and database:
        raise SecurityError("schema 和 database 不能同时传入。")

    if config.engine == "postgres":
        if database:
            raise SecurityError("PostgreSQL 连接不接受 database 参数。")
        resolved = schema or config.default_schema
        if not resolved:
            raise SecurityError("PostgreSQL 连接必须显式传 schema，或在配置中设置 default_schema。")
        return NamespaceSelection(field_name="schema", value=resolved)

    if config.engine == "mysql":
        if schema:
            raise SecurityError("MySQL 连接不接受 schema 参数。")
        resolved = database or config.default_database
        if not resolved:
            raise SecurityError("MySQL 连接必须显式传 database，或在配置中设置 default_database。")
        return NamespaceSelection(field_name="database", value=resolved)

    raise SecurityError(f"未知 engine: {config.engine}")


def require_engine(config: ConnectionConfig, engine: str, tool_name: str) -> None:
    if config.engine != engine:
        raise SecurityError(f"{tool_name} 仅适用于 {engine} 连接，当前连接 engine={config.engine}")
