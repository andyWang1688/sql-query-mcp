# OpenCode 接入说明

本文说明如何把 `sql-query-mcp` 注册到 OpenCode。它聚焦在配置和排查步骤；
如果你需要了解项目设计和 tool 行为，可以分别查看
`docs/project-overview.md` 和 `docs/api-reference.md`。

## 准备内容

开始前，请先确认你已经具备本地运行 MCP 服务的基础条件。

- Python 3.10+
- `sql-query-mcp` 仓库本地副本
- PostgreSQL 或 MySQL 只读账号
- 可编辑的 `~/.config/opencode/opencode.json`

## 第一步：安装服务

先在本地仓库中创建虚拟环境并安装项目。

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

服务默认读取 `config/connections.json`。你可以从示例文件开始。

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

如果你希望单独限制数据库执行时间，可以在 `settings` 中增加
`statement_timeout_ms`。

```json
{
  "settings": {
    "statement_timeout_ms": 15000
  }
}
```

这个超时作用在数据库会话层，不是 OpenCode 自己的会话超时。

## 第三步：准备环境变量

`connections.json` 只存环境变量名，因此你还需要准备真实 DSN 和配置路径。

```bash
export PG_CONN_CRM_PROD_MAIN_RO='postgresql://username:password@host:5432/dbname'
export MYSQL_CONN_CRM_PROD_MAIN_RO='mysql://username:password@host:3306/crm'
export SQL_QUERY_MCP_CONFIG='/absolute/path/to/sql-query-mcp/config/connections.json'
```

请保持下面这些规则一致。

- `engine` 必须显式配置
- PostgreSQL 使用 `schema`
- MySQL 使用 `database`
- `dsn_env` 必须和真实环境变量名一致

## 第四步：注册到 OpenCode

OpenCode 的全局配置文件通常位于 `~/.config/opencode/opencode.json`。在文件
中加入下面这段 MCP 配置。

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

如果你的 `opencode.json` 已经包含其他字段，只合并 `mcp` 节点即可，不要整
个文件覆盖。

## 第五步：重启 OpenCode

保存配置后，重启 OpenCode 或新开会话，让 MCP 服务重新加载。

## 第六步：验证接入

建议先跑一组最小验证动作，确认注册、连接和权限都正常。

- 查看可用连接
- 列出 PostgreSQL schema 或 MySQL database
- 查看某张业务表的结构
- 对一个简单查询执行只读测试

你可以用自然语言提示 OpenCode，例如：

- 使用 `sql_query_mcp` 工具，列出 `crm_prod_main_ro` 的 schema
- 使用 `sql_query_mcp` 工具，查看 `crm_mysql_prod_main_ro` 下 `crm.orders` 的字段信息
- 使用 `sql_query_mcp` 工具，执行查询：`select count(*) from orders`

## 常见问题

如果 OpenCode 没有正常加载 MCP，优先从配置文件合法性、路径和环境变量三类
问题入手排查。

### OpenCode 没有加载到 MCP

如果 UI 中根本没有看到 MCP 服务，通常是配置没有被正确解析。

- `~/.config/opencode/opencode.json` 是否是合法 JSON
- `command` 第一项是否指向真实可执行文件
- `enabled` 是否为 `true`

### 连接存在但查询报错

如果服务已加载，但查询失败，优先检查连接配置和数据库权限。

- `dsn_env` 和 `environment` 中的变量名是否完全一致
- 对应数据库账号是否具备目标 schema 或 database 的只读权限
- 是否把 PostgreSQL 的 `schema` 和 MySQL 的 `database` 用反了

### 查询被安全规则拦截

如果提示 SQL 不被允许，说明服务在按设计保护数据库。

- 不允许注释和多语句
- 不允许写操作和事务语句
- `EXPLAIN` 需要走 `explain_query`

## Next steps

如果 OpenCode 已经接入成功，建议继续阅读下面两个文档。

1. `docs/api-reference.md`
2. `docs/project-overview.md`
