"""Connection registry and adapter routing."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Tuple

from .adapters import MySQLAdapter, PostgresAdapter
from .config import AppConfig, ConnectionConfig
from .errors import ConfigurationError, ConnectionNotFoundError


class ConnectionRegistry:
    """Resolve connection config and route to the correct engine adapter."""

    def __init__(self, app_config: AppConfig):
        self._config = app_config
        self._adapters = {
            "postgres": PostgresAdapter(),
            "mysql": MySQLAdapter(),
        }

    def list_connections(self):
        return [item.summary for item in self._config.connections]

    def get_connection_config(self, connection_id: str) -> ConnectionConfig:
        try:
            config = self._config.connection_map[connection_id]
        except KeyError as exc:
            raise ConnectionNotFoundError(f"未知 connection_id: {connection_id}") from exc
        if not config.enabled:
            raise ConnectionNotFoundError(f"connection_id 已被禁用: {connection_id}")
        return config

    @contextmanager
    def connection(self, connection_id: str) -> Iterator[Tuple[object, ConnectionConfig, object]]:
        config = self.get_connection_config(connection_id)
        with self.connection_from_config(config) as (conn, adapter):
            yield conn, config, adapter

    @contextmanager
    def connection_from_config(self, config: ConnectionConfig) -> Iterator[Tuple[object, object]]:
        dsn = os.environ.get(config.dsn_env)
        if not dsn:
            raise ConfigurationError(
                f"{config.connection_id} 缺少环境变量 {config.dsn_env}，无法建立数据库连接"
            )
        adapter = self.get_adapter(config)
        with adapter.connection(config.connection_id, dsn) as conn:
            yield conn, adapter

    def close(self) -> None:
        for adapter in self._adapters.values():
            adapter.close()

    def get_adapter(self, config: ConnectionConfig):
        try:
            return self._adapters[config.engine]
        except KeyError as exc:
            raise ConfigurationError(f"不支持的 engine: {config.engine}") from exc
