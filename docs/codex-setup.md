# Codex 接入说明

本文说明如何把 `sql-query-mcp` 注册到 Codex。本页只覆盖接入步骤，不重复
解释项目背景和 tool 行为；如果你还不了解项目定位，先看
`docs/project-overview.md`。

## 准备内容

开始前，你需要准备本地 Python 环境、一个可访问的数据库只读账号，以及可编
辑的 `~/.codex/config.toml` 文件。

- Python 3.10+
- `pipx`
- PostgreSQL 或 MySQL 只读 DSN
- Codex 本地配置权限

## 第一步：选择运行方式

`sql-query-mcp` 在 Codex 中支持两种正式接入方式。它们的区别不在于是否可
用于生产，而在于你希望把启动责任放在哪一层。

- 安装命令模式：你先执行一次 `pipx install`，之后 Codex 直接运行
  `sql-query-mcp`
- 托管启动模式：你不预先暴露命令，而是在 Codex 配置里写入 `pipx run`
  启动链路

安装命令模式先执行下面的安装命令。

```bash
pipx install sql-query-mcp
```

托管启动模式不要求预先安装 `sql-query-mcp`，但要求本机已安装 `pipx`。
如果你想先在终端验证启动链路，可以运行：

```bash
pipx run --spec sql-query-mcp sql-query-mcp
```

如果你需要固定版本，可以把 `sql-query-mcp` 替换为
`'sql-query-mcp==X.Y.Z'`。

## 第二步：准备连接配置

通过 PyPI 安装后，服务不再依赖仓库副本。更直接的方式是把配置文件放到你
自己的目录里，并通过环境变量告诉 MCP 服务去哪里读取。

```bash
mkdir -p ~/.config/sql-query-mcp
```

把下面这份最小配置保存为
`~/.config/sql-query-mcp/connections.json`。

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

## 第三步：注册到 Codex

连接配置里的 `dsn_env` 存放的是环境变量名，不是真实连接串。因此你需要在
Codex 的 MCP 配置里同时提供配置文件路径和真实 DSN。

注意下面这些规则。

- `engine` 必须明确写成 `postgres` 或 `mysql`
- PostgreSQL 使用 `default_schema`
- MySQL 使用 `default_database`
- 不要把真实 DSN 写回 `connections.json`

打开 `~/.codex/config.toml`，然后选择下面任意一种配置。

### 安装命令模式

如果你已经执行过 `pipx install sql-query-mcp`，推荐使用这段配置。它的启
动更直接，也更容易和 `pipx upgrade` 配合。

```toml
[mcp_servers.sql_query_mcp]
command = "sql-query-mcp"
startup_timeout_sec = 20
tool_timeout_sec = 60

[mcp_servers.sql_query_mcp.env]
SQL_QUERY_MCP_CONFIG = "/Users/yourname/.config/sql-query-mcp/connections.json"
PG_CONN_CRM_PROD_MAIN_RO = "postgresql://username:password@host:5432/dbname"
MYSQL_CONN_CRM_PROD_MAIN_RO = "mysql://username:password@host:3306/crm"
```

### 托管启动模式

如果你希望把包来源直接写在 Codex 配置中，可以使用这段配置。它的效果和
`npx ...` 风格类似，只是这里使用的是 `pipx run`。

```toml
[mcp_servers.sql_query_mcp]
command = "pipx"
args = ["run", "--spec", "sql-query-mcp", "sql-query-mcp"]
startup_timeout_sec = 20
tool_timeout_sec = 60

[mcp_servers.sql_query_mcp.env]
SQL_QUERY_MCP_CONFIG = "/Users/yourname/.config/sql-query-mcp/connections.json"
PG_CONN_CRM_PROD_MAIN_RO = "postgresql://username:password@host:5432/dbname"
MYSQL_CONN_CRM_PROD_MAIN_RO = "mysql://username:password@host:3306/crm"
```

这两种方式都由 `env` 注入配置路径和真实 DSN。你只需要保留其中一种，不要
同时配置两份同名 server。

## 第四步：重启 Codex

保存配置后，重启 Codex 或新开一个会话，让新的 MCP 服务注册生效。

## 第五步：验证接入

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
- `SQL_QUERY_MCP_CONFIG` 指向的文件是否是合法 JSON
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
