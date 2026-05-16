"""Asynchronous query execution service."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .audit import AuditLogger
from .config import ServerSettings
from .errors import QueryExecutionError, sanitize_error_message
from .registry import ConnectionRegistry
from .validator import (
    build_limited_query,
    clamp_limit,
    summarize_sql,
    validate_select_sql,
)

RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
CANCELLED = "cancelled"


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _apply_statement_timeout(
    adapter: Any, conn: Any, timeout_ms: Optional[int]
) -> None:
    if timeout_ms is not None:
        getattr(adapter, "set_statement_timeout")(conn, timeout_ms)


@dataclass
class _AsyncQueryJob:
    query_id: str
    connection_id: str
    engine: str
    sql_text: str
    sql_summary: str
    applied_limit: int
    status: str = RUNNING
    columns: List[str] = field(default_factory=list)
    rows: List[object] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    cancel_callback: Optional[Callable[[], None]] = None


class AsyncQueryService:
    """Run validated read-only SQL in background worker threads."""

    def __init__(
        self,
        registry: ConnectionRegistry,
        settings: ServerSettings,
        audit_logger: AuditLogger,
        retention_seconds: int = 3600,
    ):
        self._registry = registry
        self._settings = settings
        self._audit = audit_logger
        self._retention_seconds = retention_seconds
        self._jobs: Dict[str, _AsyncQueryJob] = {}
        self._lock = threading.Lock()

    def start_query(
        self, connection_id: str, sql_text: str, limit: Optional[int] = None
    ) -> Dict[str, object]:
        started = time.perf_counter()
        config = None
        row_limit = None
        try:
            config = self._registry.get_connection_config(connection_id)
            row_limit = clamp_limit(
                limit, self._settings.default_limit, self._settings.max_limit
            )
            cleaned_sql = validate_select_sql(sql_text, config.engine)
            sql_summary = summarize_sql(cleaned_sql)
        except Exception as exc:
            duration_ms = _elapsed_ms(started)
            sanitized = sanitize_error_message(str(exc))
            self._audit.log(
                tool="start_query",
                connection_id=connection_id,
                success=False,
                duration_ms=duration_ms,
                sql_summary=summarize_sql(sql_text),
                error=sanitized,
                extra={
                    "engine": getattr(config, "engine", None),
                    "limit": row_limit,
                },
            )
            raise QueryExecutionError(sanitized) from exc

        self._cleanup_expired()
        query_id = uuid.uuid4().hex
        job = _AsyncQueryJob(
            query_id=query_id,
            connection_id=connection_id,
            engine=config.engine,
            sql_text=cleaned_sql,
            sql_summary=sql_summary,
            applied_limit=row_limit,
        )
        with self._lock:
            self._jobs[query_id] = job
        self._audit.log(
            tool="start_query",
            connection_id=connection_id,
            success=True,
            duration_ms=_elapsed_ms(started),
            sql_summary=sql_summary,
            extra={"engine": config.engine, "limit": row_limit},
        )
        thread = threading.Thread(target=self._run_query, args=(query_id,), daemon=True)
        thread.start()
        return {
            "query_id": query_id,
            "connection_id": connection_id,
            "engine": config.engine,
            "status": RUNNING,
        }

    def get_query(
        self, query_id: str, offset: int = 0, limit: Optional[int] = None
    ) -> Dict[str, object]:
        started = time.perf_counter()
        try:
            if offset < 0:
                raise QueryExecutionError("offset 必须大于等于 0。")
            with self._lock:
                job = self._get_job_locked(query_id)
                result = self._format_job_locked(job, offset, limit)
            audit_connection_id = result.get("connection_id")
            self._audit.log(
                tool="get_query",
                connection_id=(
                    audit_connection_id if isinstance(audit_connection_id, str) else None
                ),
                success=True,
                duration_ms=_elapsed_ms(started),
                sql_summary=job.sql_summary,
                extra={"engine": job.engine, "status": job.status},
            )
            return result
        except Exception as exc:
            sanitized = sanitize_error_message(str(exc))
            self._audit.log(
                tool="get_query",
                connection_id=None,
                success=False,
                duration_ms=_elapsed_ms(started),
                error=sanitized,
                extra={"query_id": query_id},
            )
            if isinstance(exc, QueryExecutionError):
                raise
            raise QueryExecutionError(sanitized) from exc

    def cancel_query(self, query_id: str) -> Dict[str, object]:
        started = time.perf_counter()
        try:
            with self._lock:
                job = self._get_job_locked(query_id)
                if job.status == RUNNING:
                    job.status = CANCELLED
                    job.updated_at = time.time()
                    if job.cancel_callback is not None:
                        job.cancel_callback()
                result: Dict[str, object] = {
                    "query_id": job.query_id,
                    "connection_id": job.connection_id,
                    "engine": job.engine,
                    "status": job.status,
                }
            self._audit.log(
                tool="cancel_query",
                connection_id=job.connection_id,
                success=True,
                duration_ms=_elapsed_ms(started),
                sql_summary=job.sql_summary,
                extra={"engine": job.engine, "status": job.status},
            )
            return result
        except Exception as exc:
            sanitized = sanitize_error_message(str(exc))
            self._audit.log(
                tool="cancel_query",
                connection_id=None,
                success=False,
                duration_ms=_elapsed_ms(started),
                error=sanitized,
                extra={"query_id": query_id},
            )
            if isinstance(exc, QueryExecutionError):
                raise
            raise QueryExecutionError(sanitized) from exc

    def job_count(self) -> int:
        with self._lock:
            return len(self._jobs)

    def _run_query(self, query_id: str) -> None:
        started = time.perf_counter()
        with self._lock:
            try:
                job = self._get_job_locked(query_id)
            except QueryExecutionError:
                return
            connection_id = job.connection_id
            engine = job.engine
            applied_limit = job.applied_limit
            sql_text = job.sql_text
            sql_summary = job.sql_summary

        try:
            config = self._registry.get_connection_config(connection_id)
            limited_sql, _ = build_limited_query(sql_text, applied_limit, engine=engine)
            with self._registry.connection_from_config(config) as (conn, adapter):
                _apply_statement_timeout(adapter, conn, self._settings.statement_timeout_ms)
                with conn.cursor() as cur:
                    with self._lock:
                        job = self._get_job_locked(query_id)
                        if job.status == CANCELLED:
                            return
                        job.cancel_callback = _build_cancel_callback(adapter, conn, cur)
                    cur.execute(limited_sql)
                    columns = adapter.column_names(cur.description)
                    rows = cur.fetchall()
            truncated = len(rows) > applied_limit
            trimmed_rows = rows[:applied_limit]
            duration_ms = _elapsed_ms(started)
            with self._lock:
                job = self._get_job_locked(query_id)
                if job.status == CANCELLED:
                    return
                job.cancel_callback = None
                job.status = SUCCEEDED
                job.columns = columns
                job.rows = trimmed_rows
                job.row_count = len(trimmed_rows)
                job.truncated = truncated
                job.duration_ms = duration_ms
                job.updated_at = time.time()
            self._audit.log(
                tool="async_query",
                connection_id=connection_id,
                success=True,
                duration_ms=duration_ms,
                row_count=len(trimmed_rows),
                sql_summary=sql_summary,
                extra={"engine": engine, "limit": applied_limit, "truncated": truncated},
            )
        except Exception as exc:
            duration_ms = _elapsed_ms(started)
            sanitized = sanitize_error_message(str(exc))
            with self._lock:
                try:
                    job = self._get_job_locked(query_id)
                except QueryExecutionError:
                    return
                if job.status == CANCELLED:
                    return
                job.cancel_callback = None
                job.status = FAILED
                job.error = sanitized
                job.duration_ms = duration_ms
                job.updated_at = time.time()
            self._audit.log(
                tool="async_query",
                connection_id=connection_id,
                success=False,
                duration_ms=duration_ms,
                sql_summary=sql_summary,
                error=sanitized,
                extra={"engine": engine, "limit": applied_limit, "truncated": False},
            )

    def _cleanup_expired(self) -> None:
        cutoff = time.time() - self._retention_seconds
        with self._lock:
            expired = [
                query_id
                for query_id, job in self._jobs.items()
                if job.status != RUNNING and job.updated_at < cutoff
            ]
            for query_id in expired:
                del self._jobs[query_id]

    def _get_job_locked(self, query_id: str) -> _AsyncQueryJob:
        try:
            return self._jobs[query_id]
        except KeyError as exc:
            raise QueryExecutionError(f"未知 query_id: {query_id}") from exc

    def _format_job_locked(
        self, job: _AsyncQueryJob, offset: int, limit: Optional[int]
    ) -> Dict[str, object]:
        result: Dict[str, object] = {
            "query_id": job.query_id,
            "connection_id": job.connection_id,
            "engine": job.engine,
            "status": job.status,
        }
        if job.status == FAILED:
            result["error"] = job.error
        if job.status != SUCCEEDED:
            return result

        page_limit = len(job.rows) if limit is None else int(limit)
        if page_limit < 0:
            raise QueryExecutionError("limit 必须大于等于 0。")
        rows = job.rows[offset : offset + page_limit]
        result.update(
            {
                "rows": rows,
                "columns": job.columns,
                "row_count": job.row_count,
                "truncated": job.truncated,
                "duration_ms": job.duration_ms,
                "applied_limit": job.applied_limit,
                "offset": offset,
                "returned_row_count": len(rows),
            }
        )
        return result


def _build_cancel_callback(adapter: Any, conn: Any, cursor: Any) -> Optional[Callable[[], None]]:
    if hasattr(adapter, "cancel_query"):
        return lambda: adapter.cancel_query(conn, cursor)
    if hasattr(cursor, "cancel"):
        return cursor.cancel
    if hasattr(conn, "cancel"):
        return conn.cancel
    return None
