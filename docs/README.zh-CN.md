# 中文入口

`sql-query-mcp` 是一个面向 AI 助手的受控 SQL MCP 服务，当前为 PostgreSQL、
MySQL 和 Hive 提供库表信息查看、样本读取、短时间有界只读查询、长时间异
步只读查询、执行计划查看，以及已有表文件导入能力。本页是中文读者的简短
入口；主 `README.md` 现在以英文为主，这里只列最相关的文档。

## 从这里开始

如果你想快速了解项目定位、接口边界或客户端接入方式，可以从下面几页开始。

- [英文主 README](../README.md)
- [项目概览](project-overview.md)
- [API 参考](api-reference.md)
- [Codex 接入说明](codex-setup.md)
- [OpenCode 接入说明](opencode-setup.md)

## 当前支持与未来方向

支持范围需要和规划中的方向分开看。

- 当前支持：PostgreSQL、MySQL 和 Hive。
- 未来方向：其他数据库适配器仍属于候选方向，当前尚未支持。
