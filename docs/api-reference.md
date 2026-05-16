# API reference (Chinese)

本文是 `sql-query-mcp` 的中文 API reference 页面。你可以在这里查到每个
tool 的适用范围、参数、返回结果和使用示例，用它来编写客户端提示词或核对
接入测试。

当前 API 一共暴露 12 个 tools，面向 AI 的多数据库发现、结构理解、受控查询
流程和受控文件导入，并在明确边界内保留当前 API 中与 PostgreSQL、MySQL 和
Hive 相关的实际行为差异。

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

这个工具适用于 MySQL 和 Hive 连接，用来列出当前用户可见的 database。

**Parameters:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | MySQL 或 Hive 连接 ID |

**Response:**

- `200`: 返回 `databases` 数组
- Error: 如果连接不是 MySQL 或 Hive，会直接拒绝

**Example:**

```json
{
  "connection_id": "crm_mysql_prod_main_ro",
  "engine": "mysql",
  "databases": ["crm", "reporting"]
}
```

## `list_tables(connection_id, schema?, database?)`

这个工具列出目标 schema 或 database 下的表和视图，并保留引擎原生命名。Hive
连接需要传 `database`，或在配置中设置 `default_database`。Hive 不接受
`schema`。

**Parameters:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | 连接 ID |
| `schema` | string | PostgreSQL conditional | PostgreSQL schema 名称 |
| `database` | string | MySQL/Hive conditional | MySQL 或 Hive database 名称 |

**Response:**

- `200`: 返回 `tables` 数组
- Error: `schema` 和 `database` 不能同时传入
- Error: PostgreSQL 不接受 `database`，MySQL 和 Hive 不接受 `schema`

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

Hive 连接需要传 `database`，或在配置中设置 `default_database`。Hive 不接受
`schema`。

**Parameters:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | 连接 ID |
| `table_name` | string | Yes | 表名 |
| `schema` | string | PostgreSQL conditional | PostgreSQL schema 名称 |
| `database` | string | MySQL/Hive conditional | MySQL 或 Hive database 名称 |

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

这个工具执行短时间、有明确返回上限的只读查询，并在服务端统一套上返回行
数限制。PostgreSQL、MySQL 和 Hive 都支持这个工具。长时间运行的只读查询
应改用 `start_query()`、`get_query()` 和 `cancel_query()`。

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

## `start_query(connection_id, sql, limit?)`

这个工具启动一个后台只读查询，适合 PostgreSQL、MySQL 和 Hive 上耗时较长
但仍然只读的 `SELECT` 或 `WITH ... SELECT` 查询。它只负责创建任务并立即返
回 `query_id`，查询结果需要通过 `get_query()` 拉取。

**Parameters:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | 连接 ID |
| `sql` | string | Yes | 只读 `SELECT` 或 `WITH ... SELECT` 查询 |
| `limit` | integer | No | 查询总返回行数上限；最终不会超过 `max_limit` |

后台执行时会额外读取 1 行用于判断 `truncated`，`applied_limit` 仍表示对外返
回的行数上限。

**Response:**

- `200`: 返回 `query_id`、`connection_id`、`engine` 和 `status`
- `status`: 初始值为 `running`
- Error: SQL 含注释、多语句、写操作或不合法语法时会被拒绝
- Error: 连接不存在、连接被禁用或数据库连接失败时会返回脱敏错误

**Example:**

```json
{
  "query_id": "8f4d2d1e8d2c4e88b8a2e2f1d7d8a3c1",
  "connection_id": "crm_prod_main_ro",
  "engine": "postgres",
  "status": "running"
}
```

## `get_query(query_id, offset?, limit?)`

这个工具查询后台任务状态，并在任务成功后分页返回结果。它适用于由
`start_query()` 创建的 PostgreSQL、MySQL 和 Hive 异步查询。

**Parameters:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `query_id` | string | Yes | `start_query()` 返回的任务 ID |
| `offset` | integer | No | 从结果集第几行开始返回；默认 `0` |
| `limit` | integer | No | 本次分页返回行数上限；不传时返回从 `offset` 开始的剩余结果 |

**Response:**

- `200`: 总是返回 `query_id`、`connection_id`、`engine` 和 `status`
- `status`: 可能为 `running`、`succeeded`、`failed` 或 `cancelled`
- `running`: 查询仍在执行，暂不返回 `rows`
- `succeeded`: 返回 `columns`、`rows`、`row_count`、`returned_row_count`、
  `offset`、`truncated`、`duration_ms` 和 `applied_limit`
- `failed`: 返回 `error`
- `cancelled`: 表示任务已取消，不返回 `rows`
- Error: `query_id` 未知或已过期时会被拒绝
- Error: `offset` 或 `limit` 小于 `0` 时会被拒绝

分页字段含义如下。

- `row_count`: 当前任务缓存的总结果行数，最多为 `applied_limit`
- `returned_row_count`: 本次响应实际返回的行数
- `offset`: 本次响应的起始行偏移
- `applied_limit`: 对外返回的总结果行数上限；后台执行会额外读取 1 行用于
  判断 `truncated`
- `truncated`: 数据库结果是否超过 `applied_limit` 并被截断

**Example:**

```json
{
  "query_id": "8f4d2d1e8d2c4e88b8a2e2f1d7d8a3c1",
  "connection_id": "crm_prod_main_ro",
  "engine": "postgres",
  "status": "succeeded",
  "columns": ["id", "status"],
  "rows": [
    {"id": 101, "status": "paid"}
  ],
  "row_count": 2,
  "returned_row_count": 1,
  "offset": 0,
  "truncated": false,
  "duration_ms": 923,
  "applied_limit": 200
}
```

## `cancel_query(query_id)`

这个工具取消一个仍在运行的后台只读查询。它适用于由 `start_query()` 创建的
PostgreSQL、MySQL 和 Hive 异步查询；如果任务已经结束，会返回当前最终状
态。

**Parameters:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `query_id` | string | Yes | `start_query()` 返回的任务 ID |

**Response:**

- `200`: 返回 `query_id`、`connection_id`、`engine` 和 `status`
- `status`: 运行中的任务返回 `cancelled`；已结束任务返回 `succeeded`、
  `failed` 或 `cancelled`
- Error: `query_id` 未知或已过期时会被拒绝

**Example:**

```json
{
  "query_id": "8f4d2d1e8d2c4e88b8a2e2f1d7d8a3c1",
  "connection_id": "crm_prod_main_ro",
  "engine": "postgres",
  "status": "cancelled"
}
```

## `explain_query(connection_id, sql, analyze?)`

这个工具对只读查询执行 `EXPLAIN`。你直接传原始 `SELECT` 即可，工具会在后
台自动包装。Hive 使用 `EXPLAIN` 和 `EXPLAIN ANALYZE`。

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

Hive 连接需要传 `database`，或在配置中设置 `default_database`。Hive 不接受
`schema`。

**Parameters:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | 连接 ID |
| `table_name` | string | Yes | 表名 |
| `schema` | string | PostgreSQL conditional | PostgreSQL schema 名称 |
| `database` | string | MySQL/Hive conditional | MySQL 或 Hive database 名称 |
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

## `import_table_file(connection_id, table_name, file_path, schema?, database?, sheet_name?)`

这个工具把 MCP server 本机路径上的 CSV 或 XLSX 文件导入到已有表。它是受控
写入入口，不接受原始 SQL，也不做字段映射、清洗、upsert、merge 或多表导
入。Hive 连接也暴露 `import_table_file`，并使用与 PostgreSQL 和 MySQL 相同
的已有表导入路径和表头校验规则。

Hive 连接需要传 `database`，或在配置中设置 `default_database`。Hive 不接受
`schema`。

**Parameters:**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | 连接 ID |
| `table_name` | string | Yes | 已存在的目标表名 |
| `file_path` | string | Yes | MCP server 本机可访问的 CSV/XLSX 文件路径 |
| `schema` | string | PostgreSQL conditional | PostgreSQL schema 名称 |
| `database` | string | MySQL/Hive conditional | MySQL 或 Hive database 名称 |
| `sheet_name` | string | No | XLSX sheet 名称；不传时读取第一个 sheet |

**Response:**

- `200`: 返回导入目标、文件类型、sheet 名称和 `inserted_row_count`
- Error: 只支持 `.csv` 和 `.xlsx` 文件
- Error: 文件表头为空、重复，或包含目标表不存在的字段时会被拒绝
- Error: 文件没有数据行时会被拒绝
- Error: XLSX 指定的 `sheet_name` 不存在时会被拒绝
- Error: 数据库约束失败时返回脱敏后的数据库错误；PostgreSQL 和 MySQL 导入
  会回滚，Hive 使用当前 HiveServer2 连接可用的执行语义

文件表头必须精确匹配目标表字段名，但可以只提供部分字段。未提供的字段交给
数据库处理，例如自增、默认值、可空字段或约束失败。

**Example:**

```json
{
  "connection_id": "crm_mysql_prod_main_rw",
  "engine": "mysql",
  "database": "crm",
  "table_name": "users",
  "inserted_row_count": 2,
  "duration_ms": 24,
  "file_extension": ".xlsx",
  "sheet_name": "Users"
}
```

## 常见调用建议

如果你是给 AI 写提示词，建议按“先结构，后查询或导入”的顺序调用，能明显
减少无效 SQL、错误导入和错误重试。

1. 先调用 `list_connections()` 确认连接 ID。
2. 再调用 `list_schemas()` 或 `list_databases()` 确认命名空间。
3. 然后调用 `list_tables()` 和 `describe_table()` 理解结构。
4. 短查询调用 `run_select()`，长时间运行的只读查询调用 `start_query()`、
   `get_query()` 和必要时的 `cancel_query()`。
5. 需要执行计划时调用 `explain_query()`，需要导入文件时调用
   `import_table_file()`。

## Next steps

如果你准备在客户端落地接入，可以继续查看对应平台文档。

1. Codex: `docs/codex-setup.md`
2. OpenCode: `docs/opencode-setup.md`
