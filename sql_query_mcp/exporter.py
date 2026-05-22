"""Controlled query result exports."""

from __future__ import annotations

import csv
import time
import uuid
from datetime import datetime, time as datetime_time, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, cast

try:
    from openpyxl import Workbook
except ImportError:  # pragma: no cover - runtime dependency
    Workbook = None

from .audit import AuditLogger
from .config import ServerSettings
from .errors import QueryExecutionError, sanitize_error_message
from .validator import clamp_limit, summarize_sql, validate_select_sql

EXPORT_BATCH_SIZE = 1000
SUPPORTED_EXPORT_ENGINES = {"postgres", "mysql"}
SUPPORTED_EXPORT_FORMATS = {"csv", "xlsx"}


class QueryExporter:
    """Export validated read-only query results to local files."""

    def __init__(self, registry: Any, settings: ServerSettings, audit_logger: AuditLogger):
        self._registry = registry
        self._settings = settings
        self._audit = audit_logger

    def export_query_file(
        self,
        connection_id: str,
        sql_text: str,
        output_path: str,
        format: str = "csv",
        limit: Optional[int] = 1000,
        export_all: bool = False,
        file_name: Optional[str] = None,
        overwrite: bool = False,
    ) -> Dict[str, object]:
        started = time.perf_counter()
        config = None
        final_path: Optional[Path] = None
        row_count = 0
        applied_limit = None
        sql_summary = summarize_sql(sql_text)
        normalized_format = str(format).lower().lstrip(".")

        try:
            if normalized_format not in SUPPORTED_EXPORT_FORMATS:
                raise QueryExecutionError("导出格式仅支持 csv 和 xlsx。")
            config = self._registry.get_connection_config(connection_id)
            if config.engine not in SUPPORTED_EXPORT_ENGINES:
                raise QueryExecutionError("export_query_file 首版仅支持 PostgreSQL 和 MySQL。")
            cleaned_sql = validate_select_sql(sql_text, config.engine)
            sql_summary = summarize_sql(cleaned_sql)
            final_path = _resolve_output_file(
                output_path,
                normalized_format,
                file_name=file_name,
                overwrite=overwrite,
            )
            query = cleaned_sql
            if not export_all:
                applied_limit = clamp_limit(limit, 1000, self._settings.max_limit)
                query = _build_exact_limited_query(cleaned_sql, applied_limit)

            with self._registry.connection_from_config(config) as (conn, adapter):
                _apply_statement_timeout(adapter, conn, self._settings.statement_timeout_ms)
                with _open_export_cursor(adapter, conn) as cur:
                    cur.execute(query)
                    columns = adapter.column_names(cur.description)
                    batches = _iter_batches(cur, columns, adapter)
                    if normalized_format == "csv":
                        row_count = _write_csv(final_path, columns, batches)
                    else:
                        row_count = _write_xlsx(final_path, columns, batches)

            duration_ms = _elapsed_ms(started)
            self._audit.log(
                tool="export_query_file",
                connection_id=connection_id,
                success=True,
                duration_ms=duration_ms,
                row_count=row_count,
                sql_summary=sql_summary,
                extra=_audit_extra(config, final_path, normalized_format, export_all, applied_limit),
            )
            return {
                "connection_id": connection_id,
                "engine": config.engine,
                "file_path": str(final_path),
                "format": normalized_format,
                "row_count": row_count,
                "duration_ms": duration_ms,
                "export_all": export_all,
                "applied_limit": applied_limit,
            }
        except Exception as exc:
            duration_ms = _elapsed_ms(started)
            sanitized = sanitize_error_message(str(exc))
            self._audit.log(
                tool="export_query_file",
                connection_id=connection_id,
                success=False,
                duration_ms=duration_ms,
                row_count=row_count,
                sql_summary=sql_summary,
                error=sanitized,
                extra=_audit_extra(config, final_path, normalized_format, export_all, applied_limit),
            )
            raise QueryExecutionError(sanitized) from exc


def _iter_batches(cur: Any, columns: Sequence[str], adapter: Any) -> Iterable[List[object]]:
    while True:
        rows = cur.fetchmany(EXPORT_BATCH_SIZE)
        if not rows:
            return
        if hasattr(adapter, "normalize_rows"):
            rows = adapter.normalize_rows(rows, list(columns))
        yield cast(List[object], rows)


def _build_exact_limited_query(sql: str, row_limit: int) -> str:
    return f"SELECT * FROM ({sql}) AS pq_result LIMIT {int(row_limit)}"


def _write_csv(path: Path, columns: Sequence[str], batches: Iterable[Sequence[object]]) -> int:
    row_count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for batch in batches:
            for row in batch:
                writer.writerow(_row_values(row, columns))
                row_count += 1
    return row_count


def _write_xlsx(path: Path, columns: Sequence[str], batches: Iterable[Sequence[object]]) -> int:
    if Workbook is None:
        raise QueryExecutionError("缺少 openpyxl 依赖，请先安装项目依赖。")
    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet("Export")
    worksheet.append(list(columns))
    row_count = 0
    for batch in batches:
        for row in batch:
            values = _row_values(row, columns, normalize_value=_normalize_xlsx_value)
            try:
                worksheet.append(values)
            except Exception as exc:
                raise QueryExecutionError(_format_xlsx_error(columns, values, exc)) from exc
            row_count += 1
    workbook.save(path)
    return row_count


def _row_values(
    row: object,
    columns: Sequence[str],
    normalize_value: Optional[Callable[[object], object]] = None,
) -> List[object]:
    if isinstance(row, dict):
        values: List[object] = [row.get(column) for column in columns]
    elif isinstance(row, (list, tuple)):
        values = list(row)
    else:
        values = [row]
    if normalize_value is None:
        return values
    return [normalize_value(value) for value in values]


def _normalize_xlsx_value(value: object) -> object:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    if isinstance(value, datetime_time) and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def _format_xlsx_error(columns: Sequence[str], values: Sequence[object], exc: Exception) -> str:
    message = str(exc) or exc.__class__.__name__
    details = ", ".join(
        f"{column}={type(value).__name__}"
        for column, value in zip(columns, values)
    )
    return f"XLSX 导出失败: {message}; columns: {details}"


def _resolve_output_file(output_path: str, format: str, file_name: Optional[str], overwrite: bool) -> Path:
    base = Path(output_path).expanduser()
    suffix = f".{format}"
    if base.exists() and base.is_dir():
        name = file_name or f"export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        candidate = base / _with_suffix(name, suffix)
    else:
        if file_name:
            raise QueryExecutionError("output_path 为文件路径时不能同时传 file_name。")
        candidate = Path(_with_suffix(str(base), suffix)).expanduser()
        if not candidate.parent.exists():
            raise QueryExecutionError("导出目录不存在。")
    if overwrite or not candidate.exists():
        return candidate
    return _next_available_path(candidate)


def _with_suffix(value: str, suffix: str) -> str:
    return value if value.lower().endswith(suffix) else value + suffix


def _next_available_path(path: Path) -> Path:
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 1
    while True:
        candidate = parent / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _apply_statement_timeout(adapter: Any, conn: Any, timeout_ms: Optional[int]) -> None:
    if timeout_ms is not None:
        getattr(adapter, "set_statement_timeout")(conn, timeout_ms)


def _open_export_cursor(adapter: Any, conn: Any) -> Any:
    export_cursor = getattr(adapter, "export_cursor", None)
    if callable(export_cursor):
        return export_cursor(conn)
    return conn.cursor()


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _audit_extra(
    config: Any,
    file_path: Optional[Path],
    format: str,
    export_all: bool,
    applied_limit: Optional[int],
) -> Dict[str, object]:
    extra: Dict[str, object] = {
        "file_path": str(file_path) if file_path is not None else None,
        "format": format,
        "export_all": export_all,
        "applied_limit": applied_limit,
    }
    if config is not None:
        extra["engine"] = config.engine
    return extra
