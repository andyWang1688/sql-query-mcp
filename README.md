# sql-query-mcp

一个面向 Codex / OpenCode / ChatGPT 的 SQL MCP 服务端，核心目标是：

- 无状态：每次调用都显式传入 `connection_id`
- 默认只读：只暴露 schema / database 浏览、表结构、只读查询、`EXPLAIN`
- 多库切换：通过 `connection_id -> DSN` 映射访问 PostgreSQL 或 MySQL
- 最小泄漏：模型永远看不到真实连接串

## 功能

- `list_connections()`
- `list_schemas(connection_id)` 仅 PostgreSQL
- `list_databases(connection_id)` 仅 MySQL
- `list_tables(connection_id, schema?, database?)`
- `describe_table(connection_id, table_name, schema?, database?)`
- `run_select(connection_id, sql, limit?)`
- `explain_query(connection_id, sql, analyze?)`
- `get_table_sample(connection_id, table_name, schema?, database?, limit?)`

## 安装

运行这个 MCP 需要 `Python 3.10+`。

```bash
cd sql-query-mcp
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

## 通用配置

1. 复制示例配置：

```bash
cp config/connections.example.json config/connections.json
```

2. 在环境变量里配置真实 DSN：

```bash
export PG_CONN_CRM_PROD_MAIN_RO='postgresql://user:password@host:5432/dbname'
export MYSQL_CONN_CRM_PROD_MAIN_RO='mysql://user:password@host:3306/crm'
```

3. 在 `config/connections.json` 中声明连接：

```json
{
  "settings": {
    "default_limit": 200,
    "max_limit": 1000,
    "statement_timeout_ms": 15000,
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

说明：

- `connection_id` 只要求是稳定且唯一的下划线命名；推荐保持 `<system>_<env>_<tenant>_<role>` 风格，需要区分同类不同连接时可增加额外段
- `engine` 只能是 `postgres` 或 `mysql`
- 服务端只读取配置中的 `engine`，不会从 `connection_id` 推断数据库类型
- `dsn_env` 填的是环境变量名，不是真实连接串
- PostgreSQL 用 `default_schema`
- MySQL 用 `default_database`
- 也可以通过 `SQL_QUERY_MCP_CONFIG` 指向自定义配置文件路径

## 客户端接入

README 只保留概要说明，详细安装与接入步骤请看：

- [Codex 接入说明](docs/codex-setup.md)
- [OpenCode 接入说明](docs/opencode-setup.md)

## 交互示例

- 用 `sql-query-mcp` 的 `crm_prod_main_ro` 连接，列出 `public` 下的表
- 用 `sql-query-mcp` 的 `crm_prod_main_ro` 连接，查看 `orders` 表结构
- 用 `sql-query-mcp` 的 `crm_mysql_prod_main_ro` 连接，列出 `crm` 数据库中的表
- 用 `sql-query-mcp` 的 `crm_mysql_prod_main_ro` 连接，查看 `orders` 表结构
- 用 `sql-query-mcp` 的 `crm_prod_main_ro` 连接，执行只读查询：统计最近 7 天每日新增用户数

## 安全限制

- 仅允许 `SELECT`、`WITH ... SELECT`
- `explain_query` 接收底层 `SELECT` 或 CTE 语句，并由服务端按引擎自动包装 `EXPLAIN`
- 拒绝多语句、注释、DDL、DML
- `run_select` 默认限制 200 行，最大 1000 行
- 默认查询超时 15 秒
- 审计日志输出到 `logs/audit.jsonl`

## 测试

```bash
cd sql-query-mcp
PYTHONPATH=. python3 -m unittest discover -s tests
```
