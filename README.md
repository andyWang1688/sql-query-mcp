# postgres-query-mcp

一个面向 Codex / ChatGPT 的 PostgreSQL MCP 服务端，核心目标是：

- 无状态：每次调用都显式传入 `connection_id`
- 默认只读：只暴露 schema 浏览、表结构、只读查询、`EXPLAIN`
- 多库切换：通过 `connection_id -> DSN` 映射访问不同 PostgreSQL 库
- 最小泄漏：模型永远看不到真实连接串

## 功能

- `list_connections()`
- `list_schemas(connection_id)`
- `list_tables(connection_id, schema?)`
- `describe_table(connection_id, table_name, schema?)`
- `run_select(connection_id, sql, limit?)`
- `explain_query(connection_id, sql, analyze?)`
- `get_table_sample(connection_id, table_name, schema?, limit?)`

## 安装

运行这个 MCP 需要 `Python 3.10+`。当前官方 `mcp` Python SDK 在 PyPI 上不支持 `Python 3.9`。

```bash
cd postgres-query-mcp
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install .
```

如果你本机的 `pip` 已经比较新，也可以改成可编辑安装：

```bash
pip install -e .
```

## 配置

1. 复制示例配置：

```bash
cp config/connections.example.json config/connections.json
```

2. 在环境变量里配置真实 DSN：

```bash
export PG_CONN_CRM_PROD_MUQIAO_RO='postgresql://user:password@host:5432/dbname'
export PG_CONN_CRM_UAT_MUQIAO_RO='postgresql://user:password@host:5432/dbname'
```

3. 按需修改 `config/connections.json`，为每个连接定义 `connection_id`、标签和默认 schema。

也可以通过环境变量指定配置文件：

```bash
export PG_QUERY_MCP_CONFIG=/absolute/path/to/connections.json
```

## 运行

默认使用 stdio transport：

```bash
cd postgres-query-mcp
source .venv/bin/activate
postgres-query-mcp
```

或：

```bash
python -m postgres_query_mcp
```

## 交互示例

面向模型的表达建议统一为：

- 用 `postgres-query-mcp` 的 `crm_prod_muqiao_ro` 连接，列出 `public` 下的表
- 用 `postgres-query-mcp` 的 `crm_uat_muqiao_ro` 连接，查看 `orders` 表结构
- 用 `postgres-query-mcp` 的 `pv_prod_demo_ro` 连接，执行只读查询：统计最近 7 天每日新增用户数

## 安全限制

- 仅允许 `SELECT`、`WITH ... SELECT`
- `explain_query` 接收底层 `SELECT` 或 CTE 语句，并由服务端自动包装 `EXPLAIN`
- 拒绝多语句、注释、DDL、DML
- `run_select` 默认限制 200 行，最大 1000 行
- 默认查询超时 15 秒
- 审计日志输出到 `logs/audit.jsonl`

## 测试

当前包含纯单元测试，覆盖配置解析和 SQL 校验逻辑：

```bash
cd postgres-query-mcp
PYTHONPATH=. python3 -m unittest discover -s tests
```
