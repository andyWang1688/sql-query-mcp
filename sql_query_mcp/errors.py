"""Error types for sql-query-mcp."""

from __future__ import annotations

import re


class SqlQueryMCPError(Exception):
    """Base error for this package."""


class ConfigurationError(SqlQueryMCPError):
    """Raised when local configuration is invalid."""


class ConnectionNotFoundError(SqlQueryMCPError):
    """Raised when the requested connection_id does not exist."""


class SecurityError(SqlQueryMCPError):
    """Raised when SQL validation rejects a query."""


class QueryExecutionError(SqlQueryMCPError):
    """Raised when the database execution layer fails."""


_DSN_CREDENTIALS_RE = re.compile(r"://([^:@/\s]+):([^@/\s]+)@")


def sanitize_error_message(message: str) -> str:
    """Mask DSN credentials before surfacing an error to the model."""

    return _DSN_CREDENTIALS_RE.sub(r"://\1:***@", message)
