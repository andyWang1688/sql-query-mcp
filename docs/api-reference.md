# API reference

本文汇总 `sql-query-mcp` 暴露的 MCP tools，包括适用引擎、参数、返回结果和
使用示例。你可以把它当作客户端提示词和接入测试时的参考手册。

## 响应约定

所有工具都返回 JSON 对象。成功时包含业务结果，失败时会返回经过脱敏的错
误信息。

常见公共字段如下。

| Field | Description |
| --- | --- |
| `connection_id` | 当前命中的连接 ID |
| `engine` | 当前连接的数据库引擎 |
| `duration_ms` | 执行耗时，部分工具返回 |
| `row_count` | 返回记录数，查询类工具返回 |

## `list_connections()`

这个工具列出所有已配置连接的摘要信息，适合让 AI 先确认有哪些连接可以用。
返回结果会保留 `enabled` 字段，因此也能看出哪些连接当前被禁用。

**Parameters:**

无。

**Response:**

- `connections`: 连接数组

**Example:**

```json
{
  "connections": [
    {
      "connection_id": "crm_prod_main_ro",
      "engine": "postgres",
      "label": "CRM PostgreSQL production read-only",
      "env": "prod",
      "tenant": "main",
      "role": "ro",
      "enabled": true,
      "default_schema": "public",
      "default_database": null,
      "description": null
    }
  ]
}
```

## `list_schemas(connection_id)`

这个工具只适用于 PostgreSQL 连接，用来列出当前用户可见的 schema。

**Parameters:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | PostgreSQL 连接 ID |

**Response:**

- `200`: 返回 `schemas` 数组
- Error: 如果连接不是 PostgreSQL，会直接拒绝

**Example:**

```json
{
  "connection_id": "crm_prod_main_ro",
  "engine": "postgres",
  "schemas": ["analytics", "public"]
}
```

## `list_databases(connection_id)`

这个工具只适用于 MySQL 连接，用来列出当前用户可见的 database。

**Parameters:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | MySQL 连接 ID |

**Response:**

- `200`: 返回 `databases` 数组
- Error: 如果连接不是 MySQL，会直接拒绝

**Example:**

```json
{
  "connection_id": "crm_mysql_prod_main_ro",
  "engine": "mysql",
  "databases": ["crm", "reporting"]
}
```

## `list_tables(connection_id, schema?, database?)`

这个工具列出目标 schema 或 database 下的表和视图，并保留引擎原生命名。

**Parameters:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | 连接 ID |
| `schema` | string | PostgreSQL conditional | PostgreSQL schema 名称 |
| `database` | string | MySQL conditional | MySQL database 名称 |

**Response:**

- `200`: 返回 `tables` 数组
- Error: `schema` 和 `database` 不能同时传入
- Error: PostgreSQL 不接受 `database`，MySQL 不接受 `schema`

**Example:**

```json
{
  "connection_id": "crm_prod_main_ro",
  "engine": "postgres",
  "schema": "public",
  "tables": [
    {
      "schema": "public",
      "table_name": "orders",
      "table_type": "BASE TABLE"
    }
  ]
}
```

## `describe_table(connection_id, table_name, schema?, database?)`

这个工具返回表字段和索引信息，适合让 AI 先理解结构再生成查询。

**Parameters:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | 连接 ID |
| `table_name` | string | Yes | 表名 |
| `schema` | string | PostgreSQL conditional | PostgreSQL schema 名称 |
| `database` | string | MySQL conditional | MySQL database 名称 |

**Response:**

- `200`: 返回 `columns` 和 `indexes`
- `404` style error: 表不存在，或当前账号没有访问权限

**Example:**

```json
{
  "connection_id": "crm_mysql_prod_main_ro",
  "engine": "mysql",
  "database": "crm",
  "table_name": "orders",
  "columns": [
    {
      "column_name": "id",
      "data_type": "bigint",
      "udt_name": null,
      "nullable": false,
      "default": null,
      "primary_key": true,
      "extra": "auto_increment"
    }
  ],
  "indexes": [
    {
      "index_name": "PRIMARY",
      "columns": ["id"],
      "unique": true,
      "primary_key": true,
      "definition": null
    }
  ]
}
```

## `run_select(connection_id, sql, limit?)`

这个工具执行只读查询，并在服务端统一套上返回行数限制。

**Parameters:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | 连接 ID |
| `sql` | string | Yes | 只读 `SELECT` 或 `WITH ... SELECT` 查询 |
| `limit` | integer | No | 返回行数上限；最终不会超过 `max_limit` |

**Response:**

- `200`: 返回 `columns`、`rows`、`row_count`、`truncated`
- Error: SQL 含注释、多语句、写操作或不合法语法时会被拒绝

`rows` 中的每一项都是对象，键名与 `columns` 对应。

**Example:**

```json
{
  "connection_id": "crm_prod_main_ro",
  "engine": "postgres",
  "columns": ["id", "status"],
  "rows": [
    {"id": 101, "status": "paid"},
    {"id": 102, "status": "pending"}
  ],
  "row_count": 2,
  "truncated": false,
  "duration_ms": 17,
  "applied_limit": 200
}
```

## `explain_query(connection_id, sql, analyze?)`

这个工具对只读查询执行 `EXPLAIN`。你直接传原始 `SELECT` 即可，工具会在后
台自动包装。

**Parameters:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | 连接 ID |
| `sql` | string | Yes | 只读 `SELECT` 或 `WITH ... SELECT` 查询 |
| `analyze` | boolean | No | 是否执行带分析的执行计划 |

**Response:**

- `200`: 返回 `plan`
- Error: MySQL 当前版本不支持 `analyze=true`
- Error: 直接传 `EXPLAIN ...` 会被拒绝

**Example:**

```json
{
  "connection_id": "crm_prod_main_ro",
  "engine": "postgres",
  "plan": [
    {
      "Plan": {
        "Node Type": "Seq Scan",
        "Relation Name": "orders"
      }
    }
  ],
  "duration_ms": 12,
  "analyze": false
}
```

## `get_table_sample(connection_id, table_name, schema?, database?, limit?)`

这个工具按目标表抽样返回少量数据，适合在生成 SQL 前理解字段内容和典型值。

**Parameters:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | 连接 ID |
| `table_name` | string | Yes | 表名 |
| `schema` | string | PostgreSQL conditional | PostgreSQL schema 名称 |
| `database` | string | MySQL conditional | MySQL database 名称 |
| `limit` | integer | No | 返回行数上限；最终不会超过 `max_limit` |

**Response:**

- `200`: 返回 `columns`、`rows`、`row_count`、`truncated`
- Error: 命名空间参数和连接引擎不匹配时会被拒绝

`rows` 中的每一项都是对象，键名与 `columns` 对应。

**Example:**

```json
{
  "connection_id": "crm_prod_main_ro",
  "engine": "postgres",
  "schema": "public",
  "table_name": "orders",
  "columns": ["id", "status"],
  "rows": [
    {"id": 101, "status": "paid"},
    {"id": 102, "status": "pending"}
  ],
  "row_count": 2,
  "truncated": false,
  "duration_ms": 9,
  "applied_limit": 50
}
```

## 常见调用建议

如果你是给 AI 写提示词，建议按“先结构，后查询”的顺序调用，能明显减少无
效 SQL 和错误重试。

1. 先调用 `list_connections()` 确认连接 ID。
2. 再调用 `list_schemas()` 或 `list_databases()` 确认命名空间。
3. 然后调用 `list_tables()` 和 `describe_table()` 理解结构。
4. 最后再调用 `run_select()` 或 `explain_query()`。

## Next steps

如果你准备在客户端落地接入，可以继续查看对应平台文档。

1. Codex: `docs/codex-setup.md`
2. OpenCode: `docs/opencode-setup.md`
