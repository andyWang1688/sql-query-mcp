# sql-query-mcp

[![GitHub stars](https://img.shields.io/github/stars/andyWang1688/sql-query-mcp?style=social)](https://github.com/andyWang1688/sql-query-mcp)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Engines](https://img.shields.io/badge/engines-PostgreSQL%20%7C%20MySQL-1f6feb)
![Mode](https://img.shields.io/badge/mode-read--only-2ea44f)
![Protocol](https://img.shields.io/badge/protocol-MCP-black)

> Read-only SQL MCP server for PostgreSQL and MySQL, built for Codex, OpenCode, and ChatGPT.

让 AI 助手安全地读取数据库，而不是直接暴露原始连接串和写权限。

`sql-query-mcp` 聚焦 4 件事：

- 显式引擎路由：`engine` 必须写在配置里，不从 `connection_id` 猜
- 清晰命名空间语义：PostgreSQL 用 `schema`，MySQL 用 `database`
- 默认安全护栏：仅允许只读查询，默认限流、超时、审计
- 客户端友好：面向 Codex / OpenCode / ChatGPT 的 MCP 接入方式

```mermaid
flowchart LR
  A["Codex / OpenCode / ChatGPT"] --> B["sql-query-mcp"]
  B --> C["connection_id + engine routing"]
  C --> D["PostgreSQL (schema)"]
  C --> E["MySQL (database)"]
```

## 为什么这个项目值得用

- 不把 `pg/mysql` 语义塞进 `connection_id`，路由逻辑更稳定
- 不把 `schema/database` 粗暴泛化成一个模糊的 `namespace`
- 不让模型直接拿到真实 DSN，降低误操作和泄漏风险
- 不开放写操作，首版只做“安全、清晰、可审计”的只读 SQL 能力

## 典型场景

- 让 Codex 列出某个 PostgreSQL `schema` 或 MySQL `database` 下的表
- 让 AI 查看表结构、索引和主键，而不需要手动查 `information_schema`
- 对只读查询做 `EXPLAIN`，快速确认执行计划
- 给模型一个统一入口，同时查询 PostgreSQL 和 MySQL

## 功能

| Tool | PostgreSQL | MySQL | 说明 |
| --- | --- | --- | --- |
| `list_connections()` | Yes | Yes | 列出已配置连接 |
| `list_schemas(connection_id)` | Yes | No | 列出可见 schema |
| `list_databases(connection_id)` | No | Yes | 列出可见 database |
| `list_tables(connection_id, schema?, database?)` | Yes | Yes | 列出表和视图 |
| `describe_table(connection_id, table_name, schema?, database?)` | Yes | Yes | 查看列、主键、索引 |
| `run_select(connection_id, sql, limit?)` | Yes | Yes | 执行只读查询 |
| `explain_query(connection_id, sql, analyze?)` | Yes | Yes | 获取执行计划 |
| `get_table_sample(connection_id, table_name, schema?, database?, limit?)` | Yes | Yes | 抽样查看表数据 |

## 安全边界

| 规则 | 默认行为 |
| --- | --- |
| SQL 类型 | 仅允许 `SELECT`、`WITH ... SELECT` |
| 注释 | 禁止 `--`、`/* */` |
| 多语句 | 禁止 |
| DDL / DML | 禁止 `INSERT`、`UPDATE`、`DELETE`、`DROP` 等 |
| 默认行数限制 | `LIMIT 200` |
| 最大行数限制 | `LIMIT 1000` |
| 数据库执行超时 | 默认沿用数据库自身配置；可用 `statement_timeout_ms` 显式覆盖 |
| 审计 | 记录 `connection_id`、`engine`、工具名、SQL 摘要、耗时、结果状态 |

SQL 会先经过 `sqlglot` 做语义解析，只读判定基于 AST，而不是简单关键字匹配；因此像 `ilike 'call %'` 这类字符串字面量不会再误报，但写操作、可写 CTE 和多语句仍会被拒绝。

## 60 秒上手

### 1. 安装

运行这个 MCP 需要 `Python 3.10+`。

```bash
cd sql-query-mcp
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

### 2. 准备连接配置

复制示例文件：

```bash
cp config/connections.example.json config/connections.json
```

最小示例：

```json
{
  "settings": {
    "default_limit": 200,
    "max_limit": 1000,
    "audit_log_path": "logs/audit.jsonl"
  },
  "connections": [
    {
      "connection_id": "crm_prod_main_ro",
      "engine": "postgres",
      "label": "CRM PostgreSQL 生产库 / 只读",
      "env": "prod",
      "tenant": "main",
      "role": "ro",
      "dsn_env": "PG_CONN_CRM_PROD_MAIN_RO",
      "enabled": true,
      "default_schema": "public"
    },
    {
      "connection_id": "crm_mysql_prod_main_ro",
      "engine": "mysql",
      "label": "CRM MySQL 生产库 / 只读",
      "env": "prod",
      "tenant": "main",
      "role": "ro",
      "dsn_env": "MYSQL_CONN_CRM_PROD_MAIN_RO",
      "enabled": true,
      "default_database": "crm"
    }
  ]
}
```

如果你想为这个 MCP 服务单独覆盖数据库执行超时，可以显式配置：

```json
{
  "settings": {
    "statement_timeout_ms": 15000
  }
}
```

说明：

- `statement_timeout_ms` 是数据库会话级执行超时，不是 MCP 客户端请求超时
- 不配置或显式设为 `null` 时，服务端不会下发超时 SQL，直接使用数据库默认值
- 客户端超时和数据库执行超时是两层配置，需要分别设置

对应环境变量：

```bash
export PG_CONN_CRM_PROD_MAIN_RO='postgresql://user:password@host:5432/dbname'
export MYSQL_CONN_CRM_PROD_MAIN_RO='mysql://user:password@host:3306/crm'
```

### 3. 在 MCP 客户端里注册

README 只保留概要说明，详细接入步骤请看：

- [Codex 接入说明](docs/codex-setup.md)
- [OpenCode 接入说明](docs/opencode-setup.md)

Codex 的最小配置片段：

```toml
[mcp_servers.sql_query_mcp]
command = "/absolute/path/to/sql-query-mcp/.venv/bin/sql-query-mcp"
type = "stdio"
startup_timeout_ms = 20000

[mcp_servers.sql_query_mcp.env]
SQL_QUERY_MCP_CONFIG = "/absolute/path/to/sql-query-mcp/config/connections.json"
PG_CONN_CRM_PROD_MAIN_RO = "postgresql://user:password@host:5432/dbname"
MYSQL_CONN_CRM_PROD_MAIN_RO = "mysql://user:password@host:3306/crm"
```

## 设计选择

- `engine` 必须显式配置为 `postgres` 或 `mysql`
- `connection_id` 只用来标识连接，不承担引擎语义
- PostgreSQL 只接受 `schema`，可回退到 `default_schema`
- MySQL 只接受 `database`，可回退到 `default_database`
- `schema` 和 `database` 同时传入一律报错

## 示例提示词

- 用 `sql-query-mcp` 的 `crm_prod_main_ro` 连接，列出 `public` 下的表
- 用 `sql-query-mcp` 的 `crm_prod_main_ro` 连接，查看 `public.orders` 表结构
- 用 `sql-query-mcp` 的 `crm_mysql_prod_main_ro` 连接，列出 `crm` 数据库中的表
- 用 `sql-query-mcp` 的 `crm_mysql_prod_main_ro` 连接，查看 `crm.orders` 表结构
- 用 `sql-query-mcp` 的 `crm_prod_main_ro` 连接，执行查询：`select count(*) from public.orders`

## 配置说明

- `connection_id` 只要求稳定且唯一；推荐保持 `<system>_<env>_<tenant>_<role>` 风格
- 服务端只读取配置中的 `engine`，不会从 `connection_id` 推断数据库类型
- `dsn_env` 填的是环境变量名，不是真实连接串
- `statement_timeout_ms` 是可选项；不写或设为 `null` 时沿用数据库默认超时
- 可通过 `SQL_QUERY_MCP_CONFIG` 指向自定义配置文件

## 测试

```bash
cd sql-query-mcp
PYTHONPATH=. python3 -m unittest discover -s tests
```

## 路线图

- 发布到 PyPI，支持 `pip install sql-query-mcp`
- 补充 Docker demo，降低首次试用门槛
- 补充更多客户端接入模板
- 提交到 MCP Registry，提升可发现性
