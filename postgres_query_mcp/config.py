"""Configuration loading for postgres-query-mcp."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .errors import ConfigurationError

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_ENV = "PG_QUERY_MCP_CONFIG"
DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "config" / "connections.json"
DEFAULT_AUDIT_LOG_PATH = PACKAGE_ROOT / "logs" / "audit.jsonl"
CONNECTION_ID_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+){3,}$")


@dataclass(frozen=True)
class ServerSettings:
    default_limit: int = 200
    max_limit: int = 1000
    statement_timeout_ms: int = 15000
    audit_log_path: Path = DEFAULT_AUDIT_LOG_PATH


@dataclass(frozen=True)
class ConnectionConfig:
    connection_id: str
    env: str
    tenant: str
    role: str
    dsn_env: str
    enabled: bool = True
    default_schemas: List[str] = field(default_factory=lambda: ["public"])
    label: Optional[str] = None
    description: Optional[str] = None

    @property
    def summary(self) -> Dict[str, object]:
        return {
            "connection_id": self.connection_id,
            "label": self.label or self.connection_id,
            "env": self.env,
            "tenant": self.tenant,
            "role": self.role,
            "enabled": self.enabled,
            "default_schemas": list(self.default_schemas),
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
    default_limit = int(data.get("default_limit", 200))
    max_limit = int(data.get("max_limit", 1000))
    statement_timeout_ms = int(data.get("statement_timeout_ms", 15000))
    audit_log_raw = data.get("audit_log_path")
    if audit_log_raw:
        audit_log_path = (path.parent / str(audit_log_raw)).resolve()
    else:
        audit_log_path = DEFAULT_AUDIT_LOG_PATH

    if default_limit <= 0:
        raise ConfigurationError("default_limit 必须大于 0")
    if max_limit < default_limit:
        raise ConfigurationError("max_limit 不能小于 default_limit")
    if statement_timeout_ms <= 0:
        raise ConfigurationError("statement_timeout_ms 必须大于 0")

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
        if not CONNECTION_ID_RE.match(connection_id):
            raise ConfigurationError(
                "connection_id 必须符合 <system>_<env>_<tenant>_<role> 风格，且只包含小写字母、数字、下划线"
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

        schemas = item.get("default_schemas") or ["public"]
        if not isinstance(schemas, list) or not all(isinstance(value, str) and value for value in schemas):
            raise ConfigurationError(f"{connection_id} 的 default_schemas 必须是非空字符串数组")

        result.append(
            ConnectionConfig(
                connection_id=connection_id,
                label=(str(item["label"]).strip() if item.get("label") else None),
                description=(str(item["description"]).strip() if item.get("description") else None),
                env=env,
                tenant=tenant,
                role=role,
                dsn_env=dsn_env,
                enabled=bool(item.get("enabled", True)),
                default_schemas=[value.strip() for value in schemas],
            )
        )

    return result
