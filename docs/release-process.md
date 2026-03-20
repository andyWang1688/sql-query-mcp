# 发布流程

本文说明 `sql-query-mcp` 的正式发布方式。目标是让每次发版都能稳定地产生
PyPI 包、GitHub Release，以及回合并到 `main` 和 `develop` 的 Pull
Request。

## Prerequisites

开始发布前，你必须先确认仓库、分支和密钥都已经准备好。缺少这些前置条件
时，不要直接打 tag。

- 当前发布从 `release/vX.Y.Z` 分支发起。
- `pyproject.toml` 中的 `project.version` 必须是 `X.Y.Z`。
- Git tag 必须使用 `vX.Y.Z`。
- GitHub Actions secret `PYPI_API_TOKEN` 必须已经配置。
- `release.yml` 必须已经在默认分支可用。

## Prepare `release/vX.Y.Z`

正式发版前，先在 release 分支完成版本收口。这里的目标是让 tag 指向一个已
经准备好对外发布的提交。

1. 从 `develop` 创建 `release/vX.Y.Z`。
2. 更新 `pyproject.toml` 版本号。
3. 同步需要反映版本变化的文档。
4. 运行测试、构建和本地 smoke test。

## Push branch, then push tag

发布触发顺序固定为先推分支，再推 tag。这样可以降低 tag workflow 启动时还
拿不到远端 release 分支的概率。

```bash
git push origin release/vX.Y.Z
git tag -a vX.Y.Z -m "Release version X.Y.Z"
git push origin vX.Y.Z
```

## Watch the release workflow

推送 tag 之后，GitHub Actions 会自动执行 `Release` workflow。你需要确认它
依次完成版本校验、测试、构建、PyPI 上传和 GitHub Release 更新。

如果 workflow 在版本校验、分支可达性或测试阶段失败，先修复问题，再重新准
备 release 提交，不要假设失败的 tag 已经完成发布。

## Verify PyPI and GitHub Release

发布成功后，你需要确认外部用户看到的结果已经齐全。这里至少检查两个出口：
PyPI 和 GitHub Release。

- 在 PyPI 上确认目标版本已经可见。
- 确认 `pip install sql-query-mcp==X.Y.Z` 可用。
- 在 GitHub 上确认 `vX.Y.Z` Release 已创建。
- 确认 Release 附件包含 `sdist` 和 `wheel`。

## Merge the back-merge PRs

发布成功后，workflow 会自动尝试创建两个回合并 PR。它们的职责不同，但都
需要你检查状态并按仓库规范合并。

- `release/vX.Y.Z -> main`：归档已发布代码。
- `release/vX.Y.Z -> develop`：把 release 阶段的版本整理和修复同步回开发分支。

如果 `develop` 没有 release-only 差异，workflow 可能不会创建回合并 PR。

## Recovery when publish succeeds but follow-up steps fail

如果 PyPI 已经成功发布，但 GitHub Release 更新或回合并 PR 创建失败，不要重
复上传同一个版本。PyPI 版本不可覆盖，这时应该走补偿流程。

1. 使用 `workflow_dispatch` 手动触发 `Release` workflow。
2. 输入目标 tag，例如 `vX.Y.Z`。
3. 明确勾选 `pypi_already_published=true`。
4. 让 workflow 只补 GitHub Release 或回合并 PR。

如果补偿执行仍然失败，就手工创建 GitHub Release 或 PR，并把失败原因记录在
本次发布的跟踪说明中。
