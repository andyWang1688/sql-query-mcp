"""Connection registry and pool management."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Tuple

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import AppConfig, ConnectionConfig
from .errors import ConfigurationError, ConnectionNotFoundError


class ConnectionRegistry:
    """Create and reuse PostgreSQL pools by connection_id."""

    def __init__(self, app_config: AppConfig):
        self._config = app_config
        self._pools = {}

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
    def connection(self, connection_id: str) -> Iterator[Tuple[object, ConnectionConfig]]:
        config = self.get_connection_config(connection_id)
        pool = self._get_pool(config)
        with pool.connection() as conn:
            yield conn, config

    def close(self) -> None:
        for pool in self._pools.values():
            pool.close()

    def _get_pool(self, config: ConnectionConfig) -> ConnectionPool:
        pool = self._pools.get(config.connection_id)
        if pool is None:
            dsn = os.environ.get(config.dsn_env)
            if not dsn:
                raise ConfigurationError(
                    f"{config.connection_id} 缺少环境变量 {config.dsn_env}，无法建立数据库连接"
                )
            pool = ConnectionPool(
                conninfo=dsn,
                min_size=0,
                max_size=4,
                open=True,
                kwargs={"autocommit": True, "row_factory": dict_row},
            )
            self._pools[config.connection_id] = pool
        return pool
