# Codex 接入说明

本文说明如何把 `sql-query-mcp` 注册到 Codex。本页只覆盖接入步骤，不重复
解释项目背景和 tool 行为；如果你还不了解项目定位，先看
`docs/project-overview.md`。

## 准备内容

开始前，你需要准备本地 Python 环境、一个可访问的数据库只读账号，以及可编
辑的 `~/.codex/config.toml` 文件。

- Python 3.10+
- `sql-query-mcp` 仓库本地副本
- PostgreSQL 或 MySQL 只读 DSN
- Codex 本地配置权限

## 第一步：安装服务

先在仓库目录中创建虚拟环境并安装项目。

```bash
cd /absolute/path/to/sql-query-mcp
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

安装完成后，可执行文件通常位于以下路径。

```bash
/absolute/path/to/sql-query-mcp/.venv/bin/sql-query-mcp
```

## 第二步：准备连接配置

服务默认读取 `config/connections.json`。你可以先复制示例文件，再按实际连
接修改。

```bash
cp config/connections.example.json config/connections.json
```

下面是一个最小配置示例。

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
      "label": "CRM PostgreSQL production read-only",
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
      "label": "CRM MySQL production read-only",
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

如果你需要为 MCP 服务单独设置数据库执行超时，可以增加
`statement_timeout_ms`。

```json
{
  "settings": {
    "statement_timeout_ms": 15000
  }
}
```

这里的超时是数据库会话级超时，不是 Codex 客户端超时。

## 第三步：准备环境变量

连接配置里的 `dsn_env` 存放的是环境变量名，不是真实连接串。因此你还需要
为对应 DSN 设置环境变量。

```bash
export PG_CONN_CRM_PROD_MAIN_RO='postgresql://username:password@host:5432/dbname'
export MYSQL_CONN_CRM_PROD_MAIN_RO='mysql://username:password@host:3306/crm'
export SQL_QUERY_MCP_CONFIG='/absolute/path/to/sql-query-mcp/config/connections.json'
```

注意下面这些配置规则。

- `engine` 必须明确写成 `postgres` 或 `mysql`
- PostgreSQL 使用 `default_schema`
- MySQL 使用 `default_database`
- 不要把真实 DSN 写回 `connections.json`

## 第四步：注册到 Codex

打开 `~/.codex/config.toml`，把下面这段配置加入 MCP servers。

```toml
[mcp_servers.sql_query_mcp]
command = "/absolute/path/to/sql-query-mcp/.venv/bin/sql-query-mcp"
type = "stdio"
startup_timeout_ms = 20000

[mcp_servers.sql_query_mcp.env]
SQL_QUERY_MCP_CONFIG = "/absolute/path/to/sql-query-mcp/config/connections.json"
PG_CONN_CRM_PROD_MAIN_RO = "postgresql://username:password@host:5432/dbname"
MYSQL_CONN_CRM_PROD_MAIN_RO = "mysql://username:password@host:3306/crm"
```

这段配置里，`command` 指向 MCP 可执行文件，`env` 注入配置路径和真实
DSN。

## 第五步：重启 Codex

保存配置后，重启 Codex 或新开一个会话，让新的 MCP 服务注册生效。

## 第六步：验证接入

接入完成后，建议先用简单问题确认服务可用，再逐步进入真实查询。

- 列出可用连接
- 列出 `crm_prod_main_ro` 的 schema
- 查看 `public.orders` 的字段和索引
- 执行一个简单 `SELECT count(*)`

如果你要更精确地写提示词，可以参考 `docs/api-reference.md`。

## 常见问题

这部分汇总了接入 Codex 时最常见的排查方向。

### 没有任何连接可用

如果 Codex 能看到 MCP 服务，但 `list_connections` 结果为空，优先检查配置装
载是否成功。

- `SQL_QUERY_MCP_CONFIG` 是否指向正确文件
- `config/connections.json` 是否是合法 JSON
- `connections.json` 是否至少有一个 `enabled: true` 的连接

### 提示缺少 DSN 环境变量

如果服务启动了，但连接时报缺少 DSN，通常是变量名没有对上。

- `dsn_env` 的值是否和 Codex `env` 段里的变量名完全一致
- 对应环境变量是否真的传入 Codex 进程

### 查询被拒绝

查询被拒绝通常不是连接失败，而是安全边界生效。

- 只接受 `SELECT` 和 `WITH ... SELECT`
- 不接受注释和多语句
- `EXPLAIN` 需要改用 `explain_query`

## Next steps

如果 Codex 接入已经完成，你可以继续做下面两件事。

1. 阅读 `docs/api-reference.md`，给 AI 提供更稳定的调用提示。
2. 阅读 `docs/project-overview.md`，理解项目内部约束和扩展点。
