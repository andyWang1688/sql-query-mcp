# sql-query-mcp

[English](README.md)

一个让 AI 在明确边界内操作多数据库的通用 MCP 服务

## 当前数据库支持

| 数据库 | 状态 | 当前可用范围 |
| --- | --- | --- |
| PostgreSQL | 已支持 | 当前可用 |
| MySQL | 已支持 | 当前可用 |
| SQLite | 候选 | 尚未支持 |
| SQL Server | 候选 | 尚未支持 |
| ClickHouse | 候选 | 尚未支持 |

## 产品价值

`sql-query-mcp` 让 AI 客户端通过一个受控的 MCP 接口了解 schema 结构、采
样数据，并分析只读查询。

它把连接处理、命名空间规则、SQL 校验和审计日志都放在服务端，因此你可以
把有价值的数据库上下文提供给 AI，而不必暴露原始连接串，也不必把不同引擎
各自的概念硬套成同一种形式。

## AI 能用它做什么

当前这组工具主要面向数据库发现和受控查询流程。你可以用它帮助 AI 助手先
理解结构，再生成或改写 SQL。

MySQL 在当前实现中支持 `explain_query`，但不支持
`explain_query(..., analyze=True)`。

| 工具 | PostgreSQL | MySQL | 用途 |
| --- | --- | --- | --- |
| `list_connections()` | 是 | 是 | 列出已配置连接 |
| `list_schemas(connection_id)` | 是 | 否 | 列出可见的 PostgreSQL schema |
| `list_databases(connection_id)` | 否 | 是 | 列出可见的 MySQL 数据库 |
| `list_tables(connection_id, schema?, database?)` | 是 | 是 | 列出表和视图 |
| `describe_table(connection_id, table_name, schema?, database?)` | 是 | 是 | 查看列、键和索引 |
| `run_select(connection_id, sql, limit?)` | 是 | 是 | 运行只读查询 |
| `explain_query(connection_id, sql, analyze?)` | 是 | 是 | 查看查询计划 |
| `get_table_sample(connection_id, table_name, schema?, database?, limit?)` | 是 | 是 | 获取小规模表样本 |

这些工具适合用于列出命名空间、检查表定义、查看索引、采样记录，以及用
`EXPLAIN` 分析只读查询。完整的请求和响应细节见 `docs/api-reference.md`。

## 边界如何被清晰限定

当前产品边界刻意保持得比较清晰。现在只有 PostgreSQL 和 MySQL 已经可用，
而且当前工具集完全是只读的。

服务通过以下几种方式明确这些边界。

- 连接必须显式声明 `engine`，因此服务端绝不会从 `connection_id` 猜测引擎。
- PostgreSQL 使用 `schema`，MySQL 使用 `database`，不会把两者强行合并成一
  个模糊的命名空间字段。
- 真实 DSN 保存在环境变量里，而配置文件只存储环境变量名。
- 查询执行在到达数据库之前会先经过 `sqlglot` 校验。
- 服务只接受 `SELECT` 和 `WITH ... SELECT`，拒绝注释和多语句输入，并为每次
  调用记录审计日志。

对 MySQL 而言，`explain_query(..., analyze=True)` 在当前实现中不可用。

## 快速开始

`sql-query-mcp` 提供两种官方支持的 PyPI 接入方式。两种都适合正式使用，不
只是本地试跑。

1. 先决定让 MCP 客户端如何启动服务。

如果你希望先安装一次，之后在客户端里直接调用命令，可以使用安装命令模式。

```bash
pipx install sql-query-mcp
```

如果你希望把包来源直接写进 MCP 配置，让客户端通过 `pipx` 启动服务，可以使
用托管启动模式。

```bash
pipx run --spec sql-query-mcp sql-query-mcp
```

如果你想固定版本，可使用 `pipx install 'sql-query-mcp==X.Y.Z'`，或者使用
`pipx run --spec 'sql-query-mcp==X.Y.Z' sql-query-mcp`。已安装版本可通过
`pipx upgrade sql-query-mcp` 升级。

2. 创建配置文件。

无论你选择哪种启动方式，都建议把服务配置文件放在仓库之外，便于统一维护。

```bash
mkdir -p ~/.config/sql-query-mcp
```

然后把本节后面的示例 JSON 保存为
`~/.config/sql-query-mcp/connections.json`。

3. 在你的 MCP 客户端中注册这个服务。

- Codex: `docs/codex-setup.md`
- OpenCode: `docs/opencode-setup.md`

安装命令模式表示客户端直接运行 `sql-query-mcp`。托管启动模式表示客户端通
过 `pipx run` 启动服务。

无论使用哪种方式，都建议把 `SQL_QUERY_MCP_CONFIG` 和真实数据库 DSN 放在
MCP 客户端的 `env` 或 `environment` 配置里，而不是单独在 shell 中导出。

对于 `pipx install` 和 `pipx run`，建议显式设置 `SQL_QUERY_MCP_CONFIG`。
默认的 `config/connections.json` 更适合源码 checkout 和本地开发场景。

示例配置如下。

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
      "label": "CRM PostgreSQL production / Main / read-only",
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
      "label": "CRM MySQL production / Main / read-only",
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

## 文档

如果你想查看实现细节、配置说明或内部结构，可以先从以下文档看起。

- `docs/project-overview.md`: 项目目标、核心概念和代码结构
- `docs/api-reference.md`: MCP 工具参考
- `docs/codex-setup.md`: Codex 配置步骤
- `docs/opencode-setup.md`: OpenCode 配置步骤
- `docs/git-workflow.md`: 仓库协作流程

## 贡献

如果你想参与贡献或查看仓库协作流程，可以先从下面这些页面开始。

- `CONTRIBUTING.md`
- `docs/roadmap.md`
- `docs/git-workflow.md`

在提交变更前运行 `PYTHONPATH=. python3 -m unittest discover -s tests`。

## 许可证

本项目采用 MIT 许可证，详见 `LICENSE`。
