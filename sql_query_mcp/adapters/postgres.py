"""PostgreSQL adapter."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, List

try:
    from psycopg import sql
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
except ImportError:  # pragma: no cover - runtime dependency
    sql = None
    dict_row = None
    ConnectionPool = None

from ..errors import ConfigurationError


class PostgresAdapter:
    engine = "postgres"

    def __init__(self) -> None:
        self._pools = {}

    @contextmanager
    def connection(self, connection_id: str, dsn: str) -> Iterator[object]:
        pool = self._get_pool(connection_id, dsn)
        with pool.connection() as conn:
            yield conn

    def close(self) -> None:
        for pool in self._pools.values():
            pool.close()

    def set_statement_timeout(self, conn: object, timeout_ms: int) -> None:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('statement_timeout', %s, false)", (str(timeout_ms),))

    def list_schemas(self, conn: object) -> List[str]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name NOT IN ('information_schema')
                  AND schema_name NOT LIKE 'pg_%'
                ORDER BY schema_name
                """
            )
            return [row["schema_name"] for row in cur.fetchall()]

    def list_tables(self, conn: object, schema: str):
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_schema AS schema, table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = %s
                ORDER BY table_name
                """,
                (schema,),
            )
            return cur.fetchall()

    def describe_table(self, conn: object, schema: str, table_name: str):
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name, data_type, udt_name, is_nullable, column_default, ordinal_position
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (schema, table_name),
            )
            columns = cur.fetchall()
            cur.execute(
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = %s
                  AND tc.table_name = %s
                ORDER BY kcu.ordinal_position
                """,
                (schema, table_name),
            )
            primary_keys = {row["column_name"] for row in cur.fetchall()}
            cur.execute(
                """
                SELECT
                    idx.relname AS index_name,
                    ix.indisunique AS is_unique,
                    ix.indisprimary AS is_primary,
                    pg_get_indexdef(ix.indexrelid) AS definition,
                    COALESCE(
                        array_agg(att.attname ORDER BY keys.ordinality)
                        FILTER (WHERE att.attname IS NOT NULL),
                        ARRAY[]::text[]
                    ) AS columns
                FROM pg_class tbl
                JOIN pg_namespace ns ON ns.oid = tbl.relnamespace
                JOIN pg_index ix ON ix.indrelid = tbl.oid
                JOIN pg_class idx ON idx.oid = ix.indexrelid
                LEFT JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS keys(attnum, ordinality) ON TRUE
                LEFT JOIN pg_attribute att
                  ON att.attrelid = tbl.oid
                 AND att.attnum = keys.attnum
                WHERE ns.nspname = %s
                  AND tbl.relname = %s
                GROUP BY idx.relname, ix.indisunique, ix.indisprimary, ix.indexrelid
                ORDER BY idx.relname
                """,
                (schema, table_name),
            )
            index_rows = cur.fetchall()

        if not columns:
            return None

        return {
            "columns": [
                {
                    "column_name": row["column_name"],
                    "data_type": row["data_type"],
                    "udt_name": row["udt_name"],
                    "nullable": row["is_nullable"] == "YES",
                    "default": row["column_default"],
                    "primary_key": row["column_name"] in primary_keys,
                }
                for row in columns
            ],
            "indexes": [
                {
                    "index_name": row["index_name"],
                    "columns": row["columns"],
                    "unique": row["is_unique"],
                    "primary_key": row["is_primary"],
                    "definition": row["definition"],
                }
                for row in index_rows
            ],
        }

    def build_sample_query(self, schema: str, table_name: str, sentinel_limit: int):
        if sql is None:
            raise ConfigurationError("缺少 psycopg 依赖，请先安装项目依赖。")
        return sql.SQL("SELECT * FROM {}.{} LIMIT {}").format(
            sql.Identifier(schema),
            sql.Identifier(table_name),
            sql.Literal(sentinel_limit),
        )

    def build_explain_query(self, sql_text: str, analyze: bool = False) -> str:
        return f"EXPLAIN (FORMAT JSON, ANALYZE {'TRUE' if analyze else 'FALSE'}) {sql_text}"

    def extract_plan(self, rows):
        return rows[0].get("QUERY PLAN", []) if rows else []

    def column_names(self, description) -> List[str]:
        return [column.name for column in (description or [])]

    def _get_pool(self, connection_id: str, dsn: str) -> ConnectionPool:
        if ConnectionPool is None or dict_row is None:
            raise ConfigurationError("缺少 psycopg / psycopg-pool 依赖，请先安装项目依赖。")
        pool = self._pools.get(connection_id)
        if pool is None:
            pool = ConnectionPool(
                conninfo=dsn,
                min_size=0,
                max_size=4,
                open=True,
                kwargs={"autocommit": True, "row_factory": dict_row},
            )
            self._pools[connection_id] = pool
        return pool
