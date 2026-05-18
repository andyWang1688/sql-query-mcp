from __future__ import annotations

import csv
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from sql_query_mcp.audit import AuditLogger
from sql_query_mcp.config import ConnectionConfig, ServerSettings
from sql_query_mcp.errors import QueryExecutionError
from sql_query_mcp.importer import TableFileImporter


class _CursorStub:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.executed = []
        self.executed_many = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def executemany(self, query, rows) -> None:
        if self._error is not None:
            raise self._error
        self.executed_many.append((query, rows))

    def execute(self, query, row=None) -> None:
        if self._error is not None:
            raise self._error
        self.executed.append((query, row))


class _HiveInsertCursorStub:
    def __init__(self, fail_on_executemany: bool = False) -> None:
        self.fail_on_executemany = fail_on_executemany
        self.executed = []
        self.executed_many = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, query, row=None) -> None:
        self.executed.append((query, row))

    def executemany(self, query, rows) -> None:
        if self.fail_on_executemany:
            raise RuntimeError("No result set")
        self.executed_many.append((query, rows))


class _ConnectionStub:
    def __init__(self, error: Exception | None = None) -> None:
        self.cursor_stub = _CursorStub(error)
        self.begin_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0

    def cursor(self) -> _CursorStub:
        return self.cursor_stub

    def begin(self) -> None:
        self.begin_calls += 1

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


class _HiveConnectionStub:
    def __init__(self, cursor: Any = None) -> None:
        self.cursor_stub = cursor or _CursorStub()

    def cursor(self) -> Any:
        return self.cursor_stub


class _AdapterStub:
    def __init__(self) -> None:
        self.set_statement_timeout_calls = []

    def set_statement_timeout(self, conn: object, timeout_ms: int) -> None:
        self.set_statement_timeout_calls.append(timeout_ms)

    def describe_table(self, conn: object, namespace: str, table_name: str):
        return {
            "columns": [
                {"column_name": "id"},
                {"column_name": "name"},
                {"column_name": "status"},
            ],
            "indexes": [],
        }

    def build_insert_query(self, namespace: str, table_name: str, columns):
        return f"insert {namespace}.{table_name} ({','.join(columns)})"


class _RegistryStub:
    def __init__(self, config: ConnectionConfig, adapter: object, conn: object) -> None:
        self._config = config
        self._adapter = adapter
        self._conn = conn

    def get_connection_config(self, connection_id: str) -> ConnectionConfig:
        if connection_id != self._config.connection_id:
            raise AssertionError(connection_id)
        return self._config

    @contextmanager
    def connection_from_config(self, config: ConnectionConfig):
        if config != self._config:
            raise AssertionError(config)
        yield self._conn, self._adapter


class TableFileImporterTestCase(unittest.TestCase):
    def test_import_csv_inserts_header_subset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_csv(
                Path(temp_dir) / "users.csv",
                [["name", "status"], ["Alice", "active"], ["Bob", "disabled"]],
            )
            conn = _ConnectionStub()
            log_path = Path(temp_dir) / "audit.jsonl"
            importer = _build_importer(log_path, conn)

            result = importer.import_table_file(
                "crm_mysql_prod_main_rw",
                "users",
                str(csv_path),
            )

            records = _read_audit_records(log_path)

        self.assertEqual(2, result["inserted_row_count"])
        self.assertEqual(".csv", result["file_extension"])
        self.assertEqual("crm", result["database"])
        self.assertEqual(1, conn.begin_calls)
        self.assertEqual(1, conn.commit_calls)
        self.assertEqual(0, conn.rollback_calls)
        self.assertEqual(
            [("insert crm.users (name,status)", [("Alice", "active"), ("Bob", "disabled")])],
            conn.cursor_stub.executed_many,
        )
        self.assertEqual("import_table_file", records[0]["tool"])
        self.assertEqual(2, records[0]["row_count"])
        self.assertEqual(".csv", records[0]["extra"]["file_extension"])

    def test_hive_import_csv_uses_existing_import_tool_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_csv(
                Path(temp_dir) / "users.csv",
                [["name", "status"], ["Alice", "active"]],
            )
            conn = _HiveConnectionStub()
            importer = _build_hive_importer(Path(temp_dir) / "audit.jsonl", conn)

            result = importer.import_table_file(
                "warehouse_hive_prod_main_rw",
                "users",
                str(csv_path),
            )

        self.assertEqual("hive", result["engine"])
        self.assertEqual("analytics", result["database"])
        self.assertEqual(1, result["inserted_row_count"])
        self.assertEqual(
            [("insert analytics.users (name,status)", ("Alice", "active"))],
            conn.cursor_stub.executed,
        )

    def test_hive_import_csv_executes_each_row_without_result_set_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_csv(
                Path(temp_dir) / "users.csv",
                [["name", "status"], ["Alice", "active"], ["Bob", "disabled"]],
            )
            cursor = _HiveInsertCursorStub(fail_on_executemany=True)
            conn = _HiveConnectionStub(cursor)
            importer = _build_hive_importer(Path(temp_dir) / "audit.jsonl", conn)

            result = importer.import_table_file(
                "warehouse_hive_prod_main_rw",
                "users",
                str(csv_path),
            )

        self.assertEqual(2, result["inserted_row_count"])
        self.assertEqual(
            [
                ("insert analytics.users (name,status)", ("Alice", "active")),
                ("insert analytics.users (name,status)", ("Bob", "disabled")),
            ],
            cursor.executed,
        )

    def test_hive_import_rejects_more_than_1000_rows_before_insert(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            rows = [["name", "status"]]
            rows.extend([f"user_{index}", "active"] for index in range(1001))
            csv_path = _write_csv(Path(temp_dir) / "users.csv", rows)
            conn = _HiveConnectionStub()
            importer = _build_hive_importer(Path(temp_dir) / "audit.jsonl", conn)

            with self.assertRaises(QueryExecutionError) as caught:
                importer.import_table_file(
                    "warehouse_hive_prod_main_rw",
                    "users",
                    str(csv_path),
                )

        self.assertIn("Hive 导入最多支持 1000 行", str(caught.exception))
        self.assertEqual([], conn.cursor_stub.executed)

    def test_import_csv_strips_utf8_bom_from_first_header(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_csv(
                Path(temp_dir) / "users.csv",
                [["id", "name"], ["1", "Alice"]],
                encoding="utf-8-sig",
            )
            conn = _ConnectionStub()
            importer = _build_importer(Path(temp_dir) / "audit.jsonl", conn)

            result = importer.import_table_file(
                "crm_mysql_prod_main_rw",
                "users",
                str(csv_path),
            )

        self.assertEqual(1, result["inserted_row_count"])
        self.assertEqual(
            [("insert crm.users (id,name)", [("1", "Alice")])],
            conn.cursor_stub.executed_many,
        )

    def test_import_csv_rejects_unknown_header_before_insert(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_csv(Path(temp_dir) / "users.csv", [["missing"], ["x"]])
            conn = _ConnectionStub()
            importer = _build_importer(Path(temp_dir) / "audit.jsonl", conn)

            with self.assertRaises(QueryExecutionError):
                importer.import_table_file("crm_mysql_prod_main_rw", "users", str(csv_path))

        self.assertEqual([], conn.cursor_stub.executed_many)
        self.assertEqual(0, conn.begin_calls)

    def test_import_csv_rejects_duplicate_header_before_insert(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_csv(Path(temp_dir) / "users.csv", [["name", "name"], ["x", "y"]])
            conn = _ConnectionStub()
            importer = _build_importer(Path(temp_dir) / "audit.jsonl", conn)

            with self.assertRaises(QueryExecutionError):
                importer.import_table_file("crm_mysql_prod_main_rw", "users", str(csv_path))

        self.assertEqual([], conn.cursor_stub.executed_many)
        self.assertEqual(0, conn.begin_calls)

    def test_import_csv_rejects_empty_header_before_insert(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_csv(Path(temp_dir) / "users.csv", [["name", ""], ["x", "y"]])
            conn = _ConnectionStub()
            importer = _build_importer(Path(temp_dir) / "audit.jsonl", conn)

            with self.assertRaises(QueryExecutionError):
                importer.import_table_file("crm_mysql_prod_main_rw", "users", str(csv_path))

        self.assertEqual([], conn.cursor_stub.executed_many)
        self.assertEqual(0, conn.begin_calls)

    def test_import_file_rejects_unsupported_extension_before_insert(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            txt_path = Path(temp_dir) / "users.txt"
            txt_path.write_text("name\nAlice\n", encoding="utf-8")
            conn = _ConnectionStub()
            importer = _build_importer(Path(temp_dir) / "audit.jsonl", conn)

            with self.assertRaises(QueryExecutionError):
                importer.import_table_file("crm_mysql_prod_main_rw", "users", str(txt_path))

        self.assertEqual([], conn.cursor_stub.executed_many)
        self.assertEqual(0, conn.begin_calls)

    def test_import_csv_rejects_file_without_data_rows_before_insert(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_csv(Path(temp_dir) / "users.csv", [["name"]])
            conn = _ConnectionStub()
            importer = _build_importer(Path(temp_dir) / "audit.jsonl", conn)

            with self.assertRaises(QueryExecutionError):
                importer.import_table_file("crm_mysql_prod_main_rw", "users", str(csv_path))

        self.assertEqual([], conn.cursor_stub.executed_many)
        self.assertEqual(0, conn.begin_calls)

    def test_import_rolls_back_when_database_insert_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_csv(Path(temp_dir) / "users.csv", [["name"], ["Alice"]])
            conn = _ConnectionStub(RuntimeError("dsn://user:secret@db failed"))
            log_path = Path(temp_dir) / "audit.jsonl"
            importer = _build_importer(log_path, conn)

            with self.assertRaises(QueryExecutionError) as caught:
                importer.import_table_file("crm_mysql_prod_main_rw", "users", str(csv_path))

            records = _read_audit_records(log_path)

        self.assertIn("dsn://user:***@db failed", str(caught.exception))
        self.assertEqual(1, conn.begin_calls)
        self.assertEqual(0, conn.commit_calls)
        self.assertEqual(1, conn.rollback_calls)
        self.assertFalse(records[0]["success"])

    def test_import_xlsx_uses_first_sheet_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            xlsx_path = _write_xlsx(Path(temp_dir) / "users.xlsx")
            conn = _ConnectionStub()
            importer = _build_importer(Path(temp_dir) / "audit.jsonl", conn)

            result = importer.import_table_file(
                "crm_mysql_prod_main_rw",
                "users",
                str(xlsx_path),
            )

        self.assertEqual("First", result["sheet_name"])
        self.assertEqual(1, result["inserted_row_count"])
        self.assertEqual(
            [("insert crm.users (name)", [("Alice",)])],
            conn.cursor_stub.executed_many,
        )

    def test_import_xlsx_uses_named_sheet_when_provided(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            xlsx_path = _write_xlsx(Path(temp_dir) / "users.xlsx")
            conn = _ConnectionStub()
            importer = _build_importer(Path(temp_dir) / "audit.jsonl", conn)

            result = importer.import_table_file(
                "crm_mysql_prod_main_rw",
                "users",
                str(xlsx_path),
                sheet_name="Data",
            )

        self.assertEqual("Data", result["sheet_name"])
        self.assertEqual(1, result["inserted_row_count"])
        self.assertEqual(
            [("insert crm.users (status)", [("active",)])],
            conn.cursor_stub.executed_many,
        )

    def test_import_xlsx_rejects_missing_sheet_before_insert(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            xlsx_path = _write_xlsx(Path(temp_dir) / "users.xlsx")
            conn = _ConnectionStub()
            importer = _build_importer(Path(temp_dir) / "audit.jsonl", conn)

            with self.assertRaises(QueryExecutionError):
                importer.import_table_file(
                    "crm_mysql_prod_main_rw",
                    "users",
                    str(xlsx_path),
                    sheet_name="Missing",
                )

        self.assertEqual([], conn.cursor_stub.executed_many)
        self.assertEqual(0, conn.begin_calls)


def _build_importer(log_path: Path, conn: _ConnectionStub) -> TableFileImporter:
    config = ConnectionConfig(
        connection_id="crm_mysql_prod_main_rw",
        engine="mysql",
        label="CRM MySQL",
        env="prod",
        tenant="main",
        role="rw",
        dsn_env="MYSQL_CONN",
        enabled=True,
        default_database="crm",
    )
    return TableFileImporter(
        registry=_RegistryStub(config, _AdapterStub(), conn),
        settings=ServerSettings(audit_log_path=log_path),
        audit_logger=AuditLogger(log_path),
    )


def _build_hive_importer(log_path: Path, conn: object) -> TableFileImporter:
    config = ConnectionConfig(
        connection_id="warehouse_hive_prod_main_rw",
        engine="hive",
        label="Warehouse Hive",
        env="prod",
        tenant="main",
        role="rw",
        dsn_env="HIVE_CONN",
        enabled=True,
        default_database="analytics",
    )
    return TableFileImporter(
        registry=_RegistryStub(config, _AdapterStub(), conn),
        settings=ServerSettings(audit_log_path=log_path),
        audit_logger=AuditLogger(log_path),
    )


def _write_csv(path: Path, rows: list[list[str]], encoding: str = "utf-8") -> Path:
    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)
    return path


def _write_xlsx(path: Path) -> Path:
    workbook = Workbook()
    first = workbook.active
    assert first is not None
    first.title = "First"
    first.append(["name"])
    first.append(["Alice"])
    second = workbook.create_sheet("Data")
    second.append(["status"])
    second.append(["active"])
    workbook.save(path)
    return path


def _read_audit_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    unittest.main()
