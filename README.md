# sql-query-mcp

只读 SQL MCP 服务，给 Codex、OpenCode、ChatGPT 等 AI 客户端提供安全的
PostgreSQL / MySQL 查询入口。

`sql-query-mcp` 的目标很简单：让 AI 助手可以读数据库结构和数据样本，但
不直接接触真实连接串、写权限，或者模糊的跨引擎命名。

## Quick start

如果你想先跑起来再看细节，可以按下面的顺序完成最小接入。默认安装路径现在
是 PyPI，而不是先 clone 仓库。

1. 使用 Python 3.10+ 创建虚拟环境并安装项目。

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install sql-query-mcp
```

如果你要安装固定版本，可以直接执行：`pip install sql-query-mcp==0.1.0`。
每个正式版本也会同步附在 GitHub Releases 中，方便回溯和下载构建产物。

2. 复制示例配置。

```bash
cp config/connections.example.json config/connections.json
```

3. 设置数据库连接串环境变量。

```bash
export PG_CONN_CRM_PROD_MUQIAO_RO='postgresql://user:password@host:5432/dbname'
export MYSQL_CONN_CRM_PROD_MUQIAO_RO='mysql://user:password@host:3306/crm'
```

4. 在 MCP 客户端里注册服务。

- Codex: 见 `docs/codex-setup.md`
- OpenCode: 见 `docs/opencode-setup.md`

补充说明：PyPI 安装名是 `sql-query-mcp`，Python 包导入路径是
`sql_query_mcp`。

## What it does

这个项目把常见的数据库只读能力封装成 MCP tools，适合让 AI 助手做结构探
索、表说明、执行计划分析，以及受限的只读查询。

| Tool | PostgreSQL | MySQL | Purpose |
| --- | --- | --- | --- |
| `list_connections()` | Yes | Yes | 列出已配置连接 |
| `list_schemas(connection_id)` | Yes | No | 列出 PostgreSQL 可见 schema |
| `list_databases(connection_id)` | No | Yes | 列出 MySQL 可见 database |
| `list_tables(connection_id, schema?, database?)` | Yes | Yes | 列出表和视图 |
| `describe_table(connection_id, table_name, schema?, database?)` | Yes | Yes | 查看列、主键、索引 |
| `run_select(connection_id, sql, limit?)` | Yes | Yes | 执行只读查询 |
| `explain_query(connection_id, sql, analyze?)` | Yes | Yes | 获取执行计划 |
| `get_table_sample(connection_id, table_name, schema?, database?, limit?)` | Yes | Yes | 获取表数据样本 |

更完整的输入输出说明见 `docs/api-reference.md`。

## Why it exists

这个项目重点解决的是“AI 可以查库，但边界必须清楚”的问题。

- `engine` 必须显式配置，服务端不会从 `connection_id` 猜数据库类型
- PostgreSQL 使用 `schema`，MySQL 使用 `database`，不混用模糊命名
- 真实 DSN 放在环境变量，配置文件只保存环境变量名
- 查询先过 `sqlglot` AST 校验，再进入数据库执行
- 默认只开放只读能力，并写入审计日志

## Configuration

配置文件默认读取 `config/connections.json`。如果你需要放到别的位置，可通
过 `SQL_QUERY_MCP_CONFIG` 指定。

```json
{
  "settings": {
    "default_limit": 200,
    "max_limit": 1000,
    "audit_log_path": "logs/audit.jsonl",
    "statement_timeout_ms": 15000
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

关键配置项如下。

| Field | Required | Description |
| --- | --- | --- |
| `connection_id` | Yes | 连接唯一标识，必须符合 `<system>_<env>_<tenant>_<role>` 风格 |
| `engine` | Yes | 仅支持 `postgres` 或 `mysql` |
| `dsn_env` | Yes | 存放真实 DSN 的环境变量名 |
| `default_schema` | PostgreSQL only | PostgreSQL 默认 schema |
| `default_database` | MySQL only | MySQL 默认 database |
| `default_limit` | No | `run_select` / `get_table_sample` 默认返回行数 |
| `max_limit` | No | 返回行数上限 |
| `statement_timeout_ms` | No | 数据库会话级执行超时 |
| `audit_log_path` | No | 审计日志输出路径 |

## Safety model

服务的核心设计是限制风险，而不是替代数据库权限管理。你仍然需要给数据库
账号配置只读权限。

| Rule | Behavior |
| --- | --- |
| SQL type | 仅接受 `SELECT` 和 `WITH ... SELECT` |
| Comments | 拒绝 `--`、`/*`、`*/` |
| Multi-statement | 拒绝多语句 |
| Mutations | 拒绝 `INSERT`、`UPDATE`、`DELETE`、`DROP` 等写操作 |
| Row limit | 默认 `200`，最大 `1000` |
| Explain | 通过 `explain_query` 包装执行，不直接接受 `EXPLAIN ...` 输入 |
| Audit | 记录工具名、连接、SQL 摘要、耗时、结果状态 |

补充说明：MySQL 首版不支持 `explain_query(..., analyze=True)`。

## Typical use cases

你可以把这个 MCP 暴露给 AI 助手做下面这些事。

- 列出某个 PostgreSQL `schema` 下的表和视图
- 列出某个 MySQL `database` 下的表
- 查看表字段、主键、索引定义
- 对只读查询执行 `EXPLAIN`
- 抽样查看数据，帮助模型理解字段语义

## Documentation

如果你要深入了解行为、接入方式和团队规范，可以从这些文档开始。

- `docs/project-overview.md`: 项目目标、核心概念、内部结构
- `docs/api-reference.md`: MCP tools 参考
- `docs/codex-setup.md`: Codex 接入步骤
- `docs/opencode-setup.md`: OpenCode 接入步骤
- `docs/release-process.md`: 发布到 PyPI 和 GitHub Release 的流程
- `docs/git-workflow.md`: 仓库 Git 协作规范

## Development

如果你要在本地修改或验证项目，这里是最短路径。这里保留 editable install，
供开发者调试和发布前验证使用。开发环境同样要求 Python 3.10+。

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
PYTHONPATH=. python3 -m unittest discover -s tests
```

项目入口在 `sql_query_mcp/app.py`，核心模块如下。

- `sql_query_mcp/config.py`: 配置加载与校验
- `sql_query_mcp/validator.py`: SQL 只读校验
- `sql_query_mcp/introspection.py`: 元数据查询
- `sql_query_mcp/executor.py`: 查询执行与限流
- `sql_query_mcp/adapters/`: PostgreSQL / MySQL 适配层

## Contributing

当前仓库还没有独立的贡献指南。提交改动前，建议先阅读 `AGENT.md` 和
`docs/git-workflow.md`，并确保相关测试通过。

## License

本项目使用 MIT License，完整文本见 `LICENSE`。
