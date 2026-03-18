# OpenCode 接入说明

本文说明如何把 `sql-query-mcp` 接入 OpenCode。

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

如果你要为这个 MCP 服务单独覆盖数据库执行超时，可以额外加上：

```json
{
  "settings": {
    "statement_timeout_ms": 15000
  }
}
```

说明：

- `statement_timeout_ms` 是数据库会话级执行超时，不是 OpenCode 的客户端请求超时
- 不配置或显式设为 `null` 时，服务端不会下发超时设置，直接沿用数据库默认值
- 客户端超时和数据库执行超时是两层配置，需要分别设置

准备对应 DSN 环境变量值：

```bash
export PG_CONN_CRM_PROD_MAIN_RO='postgresql://username:password@host:5432/dbname'
export MYSQL_CONN_CRM_PROD_MAIN_RO='mysql://username:password@host:3306/crm'
```

补充说明：

- `engine` 必须显式写在 `connections.json` 里，服务端不会从 `connection_id` 推断数据库类型
- `connection_id` 推荐保持稳定的下划线命名；如需区分同类不同连接，可以增加额外段，但不要依赖其中的 `pg/mysql` 字样做路由
- SQL 校验基于 `sqlglot` 语义解析，只接受只读 `SELECT` / `WITH ... SELECT`，不会因为字符串字面量里出现 `call`、`delete` 之类的单词而误拦截

## 3. 在 OpenCode 中注册 MCP

根据 OpenCode 官方文档，全局配置文件放在：

```bash
~/.config/opencode/opencode.json
```

在这个文件中加入：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "sql_query_mcp": {
      "type": "local",
      "command": [
        "/absolute/path/to/sql-query-mcp/.venv/bin/sql-query-mcp"
      ],
      "enabled": true,
      "environment": {
        "SQL_QUERY_MCP_CONFIG": "/absolute/path/to/sql-query-mcp/config/connections.json",
        "PG_CONN_CRM_PROD_MAIN_RO": "postgresql://username:password@host:5432/dbname",
        "MYSQL_CONN_CRM_PROD_MAIN_RO": "mysql://username:password@host:3306/crm"
      }
    }
  }
}
```

说明：

- `type: "local"` 表示 OpenCode 启动本地 MCP 进程
- `command` 是命令数组，第一项就是可执行文件路径
- `environment` 用于传入配置文件路径和真实 DSN
- 如果你的 `opencode.json` 已经有别的配置项，只需要把 `mcp` 这一段合并进去，不要整文件覆盖

## 4. 重启 OpenCode

保存 `~/.config/opencode/opencode.json` 后，重启 OpenCode 或新开会话。

## 5. 在对话中使用

你可以直接这样说：

- 使用 `sql_query_mcp` 工具，列出 `crm_prod_main_ro` 的 schema
- 使用 `sql_query_mcp` 工具，查看 `crm_prod_main_ro` 下 `public.orders` 的字段信息
- 使用 `sql_query_mcp` 工具，列出 `crm_mysql_prod_main_ro` 的 database
- 使用 `sql_query_mcp` 工具，查看 `crm_mysql_prod_main_ro` 下 `crm.orders` 的字段信息
- 使用 `sql_query_mcp` 工具，执行查询：`select count(*) from orders`

## 常见问题

### OpenCode 没有加载到 MCP

优先检查：

- `~/.config/opencode/opencode.json` 是否是合法 JSON
- `command` 路径是否可执行
- `environment` 中的 `SQL_QUERY_MCP_CONFIG` 是否指向正确文件

### 连接存在但查询报错

优先检查：

- `connections.json` 中的 `dsn_env` 和 `environment` 里的变量名是否一致
- 对应数据库账号是否真的有只读权限
- SQL 是否违反了当前服务的只读限制
