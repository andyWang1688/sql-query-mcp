"""Audit logging utilities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class AuditLogger:
    """Write audit records as JSON lines."""

    def __init__(self, log_path: Path):
        self._log_path = Path(log_path)

    def log(
        self,
        *,
        tool: str,
        connection_id: Optional[str],
        success: bool,
        duration_ms: int,
        row_count: Optional[int] = None,
        sql_summary: Optional[str] = None,
        error: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "connection_id": connection_id,
            "success": success,
            "duration_ms": duration_ms,
            "row_count": row_count,
            "sql_summary": sql_summary,
            "error": error,
            "extra": extra or {},
        }
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
