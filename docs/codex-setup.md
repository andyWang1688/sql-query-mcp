# Codex 接入说明

本文说明如何把 `postgres-query-mcp` 接入 Codex。

## 1. 安装 MCP 服务

```bash
cd /absolute/path/to/postgres-query-mcp
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

安装完成后，可执行文件通常位于：

```bash
/absolute/path/to/postgres-query-mcp/.venv/bin/postgres-query-mcp
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
      "label": "CRM 生产库 / 只读",
      "env": "prod",
      "tenant": "main",
      "role": "ro",
      "dsn_env": "PG_CONN_CRM_PROD_MAIN_RO",
      "enabled": true,
      "default_schemas": ["public"]
    }
  ]
}
```

然后准备对应的环境变量：

```bash
export PG_CONN_CRM_PROD_MAIN_RO='postgresql://username:password@host:5432/dbname'
```

也可以通过环境变量指定配置文件位置：

```bash
export PG_QUERY_MCP_CONFIG=/absolute/path/to/postgres-query-mcp/config/connections.json
```

## 3. 在 Codex 中注册 MCP

编辑 `~/.codex/config.toml`，加入：

```toml
[mcp_servers.postgres_query_mcp]
command = "/absolute/path/to/postgres-query-mcp/.venv/bin/postgres-query-mcp"
type = "stdio"
startup_timeout_ms = 20000

[mcp_servers.postgres_query_mcp.env]
PG_QUERY_MCP_CONFIG = "/absolute/path/to/postgres-query-mcp/config/connections.json"
PG_CONN_CRM_PROD_MAIN_RO = "postgresql://username:password@host:5432/dbname"
PG_CONN_CRM_UAT_MAIN_RO = "postgresql://username:password@host:5432/dbname"
```

说明：

- `command` 指向虚拟环境中的可执行文件
- `type = "stdio"` 表示用本地进程方式启动 MCP
- 真实 DSN 建议通过 `env` 注入，不要写进 `connections.json`

## 4. 重启 Codex

保存配置后，重启 Codex 或新开会话，让新的 MCP 配置生效。

## 5. 在对话中使用

可以直接这样说：

- 用 `postgres-query-mcp` 的 `crm_prod_main_ro` 连接，列出 `public` 下的表
- 用 `postgres-query-mcp` 的 `crm_prod_main_ro` 连接，查看 `orders` 表结构
- 用 `postgres-query-mcp` 的 `crm_prod_main_ro` 连接，执行查询：`select count(*) from orders`
- 用 `postgres-query-mcp` 的 `crm_prod_main_ro` 连接，对下面这条 SQL 做 `EXPLAIN`：`select * from orders where created_at >= now() - interval '7 days'`

## 常见问题

### 没有任何连接可用

通常是下面几种原因：

- `config/connections.json` 路径不对
- `PG_QUERY_MCP_CONFIG` 没有正确传进去
- `connections.json` 里没有启用任何连接

### 提示缺少 DSN 环境变量

检查 `connections.json` 中的 `dsn_env` 是否和 `config.toml` 里的环境变量名完全一致。

### 查询被拒绝

这是预期行为。当前版本默认只允许：

- `SELECT`
- `WITH ... SELECT`
- `EXPLAIN` 需要通过工具 `explain_query` 间接执行
