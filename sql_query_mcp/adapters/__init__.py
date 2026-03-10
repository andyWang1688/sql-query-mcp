"""Engine adapters for sql-query-mcp."""

__all__ = ["MySQLAdapter", "PostgresAdapter"]


def __getattr__(name: str):
    if name == "MySQLAdapter":
        from .mysql import MySQLAdapter

        return MySQLAdapter
    if name == "PostgresAdapter":
        from .postgres import PostgresAdapter

        return PostgresAdapter
    raise AttributeError(name)
