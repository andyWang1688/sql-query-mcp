from __future__ import annotations

import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from sql_query_mcp.async_queries import AsyncQueryService
from sql_query_mcp.audit import AuditLogger
from sql_query_mcp.config import ConnectionConfig, ServerSettings
from sql_query_mcp.errors import QueryExecutionError
from sql_query_mcp.registry import ConnectionRegistry


class _QueryAdapterStub:
    def __init__(self) -> None:
        self.set_statement_timeout_calls = []

    def set_statement_timeout(self, conn: object, timeout_ms: int) -> None:
        self.set_statement_timeout_calls.append(timeout_ms)

    def column_names(self, description):
        return list(description)


class _CursorStub:
    def __init__(self, rows, description=None, block: bool = False) -> None:
        self._rows = rows
        self.description = description or ["id"]
        self.executed = []
        self.block = block
        self.started = threading.Event()
        self.release = threading.Event()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str) -> None:
        self.executed.append(sql)
        self.started.set()
        if self.block:
            self.release.wait(1)

    def fetchall(self):
        return self._rows


class _ConnectionStub:
    def __init__(self, cursor: _CursorStub) -> None:
        self._cursor = cursor

    def cursor(self) -> _CursorStub:
        return self._cursor


class _RegistryStub:
    def __init__(self, config: ConnectionConfig, adapter: object, conn: object) -> None:
        self._config = config
        self._adapter = adapter
        self._conn = conn
        self.connection_calls = 0

    def get_connection_config(self, connection_id: str) -> ConnectionConfig:
        if connection_id != self._config.connection_id:
            raise AssertionError(connection_id)
        return self._config

    @contextmanager
    def connection_from_config(self, config: ConnectionConfig):
        if config != self._config:
            raise AssertionError(config)
        self.connection_calls += 1
        yield self._conn, self._adapter


def _build_service(rows=None, description=None, cursor=None, engine="hive", block=False):
    config = ConnectionConfig(
        connection_id="warehouse_hive_prod_main_ro",
        engine=engine,
        label="Warehouse Hive",
        env="prod",
        tenant="main",
        role="ro",
        dsn_env="HIVE_CONN",
        enabled=True,
        default_database="default",
    )
    cursor = cursor or _CursorStub(rows or [], description=description, block=block)
    adapter = _QueryAdapterStub()
    registry = _RegistryStub(config, adapter, _ConnectionStub(cursor))
    temp_dir = tempfile.TemporaryDirectory()
    service = AsyncQueryService(
        registry=cast(ConnectionRegistry, registry),
        settings=ServerSettings(
            default_limit=200,
            max_limit=1000,
            statement_timeout_ms=2500,
            audit_log_path=Path(temp_dir.name) / "audit.jsonl",
        ),
        audit_logger=AuditLogger(Path(temp_dir.name) / "audit.jsonl"),
    )
    return service, temp_dir, cursor


def _wait_for_done(service: AsyncQueryService, query_id: str):
    deadline = time.time() + 2
    while time.time() < deadline:
        result = service.get_query(query_id)
        if result["status"] != "running":
            return result
        time.sleep(0.01)
    raise AssertionError("query did not finish")


class AsyncQueryServiceTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        temp_dir = getattr(self, "temp_dir", None)
        if temp_dir is not None:
            temp_dir.cleanup()

    def test_start_query_returns_running_and_get_query_returns_rows_after_completion(self) -> None:
        service, self.temp_dir, _ = _build_service(
            rows=[{"id": 1}, {"id": 2}], description=["id"]
        )

        started = service.start_query("warehouse_hive_prod_main_ro", "SELECT 1", limit=1)
        query_id = cast(str, started["query_id"])
        result = _wait_for_done(service, query_id)

        self.assertEqual("running", started["status"])
        self.assertEqual("succeeded", result["status"])
        self.assertEqual([{"id": 1}], result["rows"])
        self.assertTrue(result["truncated"])
        self.assertEqual(1, result["returned_row_count"])

    def test_start_query_rejects_invalid_sql_before_creating_job(self) -> None:
        service, self.temp_dir, _ = _build_service(rows=[])

        with self.assertRaises(QueryExecutionError):
            service.start_query("warehouse_hive_prod_main_ro", "DELETE FROM users")

        self.assertEqual(0, service.job_count())

    def test_get_query_paginates_completed_results(self) -> None:
        service, self.temp_dir, _ = _build_service(
            rows=[{"id": 1}, {"id": 2}, {"id": 3}], description=["id"]
        )
        query_id = cast(str, service.start_query(
            "warehouse_hive_prod_main_ro", "SELECT 1", limit=3
        )["query_id"])
        _wait_for_done(service, query_id)

        page = service.get_query(query_id, offset=1, limit=1)

        self.assertEqual([{"id": 2}], page["rows"])
        self.assertEqual(1, page["offset"])
        self.assertEqual(1, page["returned_row_count"])

    def test_cancel_query_marks_running_job_cancelled(self) -> None:
        service, self.temp_dir, cursor = _build_service(rows=[{"id": 1}], block=True)
        query_id = cast(
            str,
            service.start_query("warehouse_hive_prod_main_ro", "SELECT 1")["query_id"],
        )
        cursor.started.wait(1)

        cancelled = service.cancel_query(query_id)

        self.assertEqual("cancelled", cancelled["status"])
        self.assertEqual("cancelled", service.get_query(query_id)["status"])
        cursor.release.set()
        time.sleep(0.05)
        self.assertEqual("cancelled", service.get_query(query_id)["status"])

    def test_hive_async_query_uses_portable_wrapper(self) -> None:
        cursor = _CursorStub(rows=[{"id": 1}], description=["id"])
        service, self.temp_dir, _ = _build_service(cursor=cursor, engine="hive")

        query_id = cast(
            str,
            service.start_query("warehouse_hive_prod_main_ro", "SELECT 1", limit=1)[
                "query_id"
            ],
        )
        _wait_for_done(service, query_id)

        self.assertEqual(["SELECT * FROM (SELECT 1) AS pq_result LIMIT 2"], cursor.executed)


if __name__ == "__main__":
    unittest.main()
