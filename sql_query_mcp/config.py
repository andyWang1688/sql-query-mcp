"""Configuration loading for sql-query-mcp."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .errors import ConfigurationError

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_ENV = "SQL_QUERY_MCP_CONFIG"
DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "config" / "connections.json"
DEFAULT_AUDIT_LOG_PATH = PACKAGE_ROOT / "logs" / "audit.jsonl"
CONNECTION_ID_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+){3,}$")
SUPPORTED_ENGINES = {"postgres", "mysql"}


@dataclass(frozen=True)
class ServerSettings:
    default_limit: int = 200
    max_limit: int = 1000
    statement_timeout_ms: Optional[int] = None
    audit_log_path: Path = DEFAULT_AUDIT_LOG_PATH


@dataclass(frozen=True)
class ConnectionConfig:
    connection_id: str
    engine: str
    env: str
    tenant: str
    role: str
    dsn_env: str
    enabled: bool = True
    label: Optional[str] = None
    description: Optional[str] = None
    default_schema: Optional[str] = None
    default_database: Optional[str] = None

    @property
    def summary(self) -> Dict[str, object]:
        return {
            "connection_id": self.connection_id,
            "engine": self.engine,
            "label": self.label or self.connection_id,
            "env": self.env,
            "tenant": self.tenant,
            "role": self.role,
            "enabled": self.enabled,
            "default_schema": self.default_schema,
            "default_database": self.default_database,
            "description": self.description,
        }


@dataclass(frozen=True)
class AppConfig:
    settings: ServerSettings
    connections: List[ConnectionConfig]

    @property
    def connection_map(self) -> Dict[str, ConnectionConfig]:
        return {item.connection_id: item for item in self.connections}

    def enabled_connections(self) -> Iterable[ConnectionConfig]:
        return (item for item in self.connections if item.enabled)


def resolve_config_path(config_path: Optional[str] = None) -> Path:
    raw_path = config_path or os.environ.get(DEFAULT_CONFIG_ENV)
    return Path(raw_path).expanduser().resolve() if raw_path else DEFAULT_CONFIG_PATH


def load_config(config_path: Optional[str] = None) -> AppConfig:
    path = resolve_config_path(config_path)
    if not path.exists():
        return AppConfig(settings=ServerSettings(), connections=[])

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"配置文件不是有效 JSON: {path}") from exc

    settings = _parse_settings(payload.get("settings", {}), path)
    connections = _parse_connections(payload.get("connections", []))
    return AppConfig(settings=settings, connections=connections)


def _parse_settings(data: Dict[str, object], path: Path) -> ServerSettings:
    default_limit = _required_int(data.get("default_limit", 200), "default_limit")
    max_limit = _required_int(data.get("max_limit", 1000), "max_limit")
    statement_timeout_ms = _optional_positive_int(
        data.get("statement_timeout_ms"), "statement_timeout_ms"
    )
    audit_log_raw = str(
        data.get("audit_log_path", DEFAULT_AUDIT_LOG_PATH.relative_to(PACKAGE_ROOT))
    )
    audit_log_path = Path(audit_log_raw)
    if not audit_log_path.is_absolute():
        audit_log_path = (path.parent / audit_log_path).resolve()

    if default_limit <= 0:
        raise ConfigurationError("default_limit 必须大于 0")
    if max_limit < default_limit:
        raise ConfigurationError("max_limit 不能小于 default_limit")
    return ServerSettings(
        default_limit=default_limit,
        max_limit=max_limit,
        statement_timeout_ms=statement_timeout_ms,
        audit_log_path=audit_log_path,
    )


def _parse_connections(items: object) -> List[ConnectionConfig]:
    if not isinstance(items, list):
        raise ConfigurationError("connections 必须是数组")

    result: List[ConnectionConfig] = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise ConfigurationError("connections 数组中的每一项都必须是对象")

        connection_id = str(item.get("connection_id", "")).strip()
        engine = str(item.get("engine", "")).strip()
        label = _required_string(item, "label", connection_id or "connection")
        enabled = _required_bool(item, "enabled", connection_id or "connection")
        if not CONNECTION_ID_RE.match(connection_id):
            raise ConfigurationError(
                "connection_id 必须符合 <system>_<env>_<tenant>_<role> 风格，且只包含小写字母、数字、下划线"
            )
        if engine not in SUPPORTED_ENGINES:
            raise ConfigurationError(
                f"{connection_id} 缺少合法 engine，必须是 postgres 或 mysql"
            )
        if connection_id in seen:
            raise ConfigurationError(f"重复的 connection_id: {connection_id}")
        seen.add(connection_id)

        dsn_env = str(item.get("dsn_env", "")).strip()
        env = str(item.get("env", "")).strip()
        tenant = str(item.get("tenant", "")).strip()
        role = str(item.get("role", "")).strip()
        if not all((dsn_env, env, tenant, role)):
            raise ConfigurationError(
                f"{connection_id} 缺少必要字段，必须提供 env / tenant / role / dsn_env"
            )

        _reject_legacy_namespace_fields(item, connection_id)
        default_schema = _optional_string(item.get("default_schema"))
        default_database = _optional_string(item.get("default_database"))

        if engine == "postgres" and "default_database" in item:
            raise ConfigurationError(
                f"{connection_id} 是 PostgreSQL 连接，不能配置 default_database"
            )
        if engine == "mysql" and "default_schema" in item:
            raise ConfigurationError(
                f"{connection_id} 是 MySQL 连接，不能配置 default_schema"
            )

        result.append(
            ConnectionConfig(
                connection_id=connection_id,
                engine=engine,
                label=label,
                description=(
                    str(item["description"]).strip()
                    if item.get("description")
                    else None
                ),
                env=env,
                tenant=tenant,
                role=role,
                dsn_env=dsn_env,
                enabled=enabled,
                default_schema=default_schema,
                default_database=default_database,
            )
        )

    return result


def _reject_legacy_namespace_fields(
    item: Dict[str, object], connection_id: str
) -> None:
    if "default_namespace" in item:
        raise ConfigurationError(
            f"{connection_id} 仍在使用 default_namespace，请改为 default_schema 或 default_database"
        )
    if "default_schemas" in item:
        raise ConfigurationError(
            f"{connection_id} 仍在使用 default_schemas，请收敛为单值字段 default_schema"
        )


def _optional_string(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_positive_int(value: Any, field_name: str) -> Optional[int]:
    if value is None:
        return None
    parsed = _required_int(value, field_name)
    if parsed <= 0:
        raise ConfigurationError(f"{field_name} 必须是大于 0 的整数")
    return parsed


def _required_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ConfigurationError(f"{field_name} 必须是整数")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise ConfigurationError(f"{field_name} 必须是整数")
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ConfigurationError(f"{field_name} 必须是整数") from exc
    try:
        return value.__int__()
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{field_name} 必须是整数") from exc


def _required_string(
    item: Dict[str, object], field_name: str, connection_id: str
) -> str:
    value = _optional_string(item.get(field_name))
    if value is None:
        raise ConfigurationError(f"{connection_id} 缺少必要字段 {field_name}")
    return value


def _required_bool(
    item: Dict[str, object], field_name: str, connection_id: str
) -> bool:
    if field_name not in item:
        raise ConfigurationError(f"{connection_id} 缺少必要字段 {field_name}")
    value = item[field_name]
    if not isinstance(value, bool):
        raise ConfigurationError(f"{connection_id} 的 {field_name} 必须是布尔值")
    return value
