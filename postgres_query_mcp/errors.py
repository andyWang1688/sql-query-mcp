"""Error types for postgres-query-mcp."""

from __future__ import annotations

import re


class PostgresQueryMCPError(Exception):
    """Base error for this package."""


class ConfigurationError(PostgresQueryMCPError):
    """Raised when local configuration is invalid."""


class ConnectionNotFoundError(PostgresQueryMCPError):
    """Raised when the requested connection_id does not exist."""


class SecurityError(PostgresQueryMCPError):
    """Raised when SQL validation rejects a query."""


class QueryExecutionError(PostgresQueryMCPError):
    """Raised when the database execution layer fails."""


_DSN_CREDENTIALS_RE = re.compile(r"://([^:@/\s]+):([^@/\s]+)@")


def sanitize_error_message(message: str) -> str:
    """Mask DSN credentials before surfacing an error to the model."""

    return _DSN_CREDENTIALS_RE.sub(r"://\1:***@", message)
