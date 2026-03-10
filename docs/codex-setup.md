# Codex 接入说明

本文说明如何把 `sql-query-mcp` 接入 Codex。

## 1. 安装 MCP 服务

```bash
cd /absolute/path/to/sql-query-mcp
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

安装完成后，可执行文件通常位于：

```bash
/absolute/path/to/sql-query-mcp/.venv/bin/sql-query-mcp
```

## 2. 准备连接配置

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

然后准备对应的环境变量：

```bash
export PG_CONN_CRM_PROD_MAIN_RO='postgresql://username:password@host:5432/dbname'
export MYSQL_CONN_CRM_PROD_MAIN_RO='mysql://username:password@host:3306/crm'
```

也可以通过环境变量指定配置文件位置：

```bash
export SQL_QUERY_MCP_CONFIG=/absolute/path/to/sql-query-mcp/config/connections.json
```

补充说明：

- `engine` 必须显式写在 `connections.json` 里，服务端不会从 `connection_id` 推断数据库类型
- `connection_id` 推荐保持稳定的下划线命名；如需区分同类不同连接，可以增加额外段，但不要依赖其中的 `pg/mysql` 字样做路由

## 3. 在 Codex 中注册 MCP

编辑 `~/.codex/config.toml`，加入：

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

说明：

- `command` 指向虚拟环境中的可执行文件
- `type = "stdio"` 表示用本地进程方式启动 MCP
- 真实 DSN 建议通过 `env` 注入，不要写进 `connections.json`

## 4. 重启 Codex

保存配置后，重启 Codex 或新开会话，让新的 MCP 配置生效。

## 5. 在对话中使用

可以直接这样说：

- 用 `sql-query-mcp` 的 `crm_prod_main_ro` 连接，列出 `public` 下的表
- 用 `sql-query-mcp` 的 `crm_prod_main_ro` 连接，查看 `public.orders` 表结构
- 用 `sql-query-mcp` 的 `crm_mysql_prod_main_ro` 连接，列出 `crm` 数据库中的表
- 用 `sql-query-mcp` 的 `crm_mysql_prod_main_ro` 连接，查看 `crm.orders` 表结构
- 用 `sql-query-mcp` 的 `crm_prod_main_ro` 连接，执行查询：`select count(*) from public.orders`

## 常见问题

### 没有任何连接可用

通常是下面几种原因：

- `config/connections.json` 路径不对
- `SQL_QUERY_MCP_CONFIG` 没有正确传进去
- `connections.json` 里没有启用任何连接

### 提示缺少 DSN 环境变量

检查 `connections.json` 中的 `dsn_env` 是否和 `config.toml` 里的环境变量名完全一致。

### 查询被拒绝

这是预期行为。当前版本默认只允许：

- `SELECT`
- `WITH ... SELECT`
- `EXPLAIN` 需要通过工具 `explain_query` 间接执行
