# Git 使用规范

本文定义本仓库的 Git 分支模型、发布流程和 AI 协作边界。无论是人工开发，还
是 AI 工具参与修改，都需要优先遵循这里的约束。

## 文档目的

这份规范的目标是统一协作方式，减少分支混乱、历史污染和发布回溯困难。

- 保持 `main` 对应生产环境已发布代码
- 保持 `develop` 作为默认开发集成分支
- 用清晰分支模型承载功能开发、发布准备和紧急修复
- 避免把客户定制需求长期堆积到主干仓库

## 核心分支模型

本项目采用接近 Git Flow 的分支策略，但只保留当前仓库真正需要的角色。

| Branch | Purpose | Rule |
| --- | --- | --- |
| `main` | 生产分支 | 不直接提交，不直接 push |
| `develop` | 默认开发集成分支 | 新功能的合并目标 |
| `feature/<name>` | 新功能开发 | 从 `develop` 创建，完成后合并回 `develop` |
| `release/vX.Y.Z` | 发布准备 | 从 `develop` 创建，用于收口测试和版本整理 |
| `hotfix/<issue-id>` | 紧急修复 | 从 `main` 创建，完成后同时合并回 `main` 和 `develop` |

## 日常开发流程

如果你在开发普通需求，默认按照功能分支流程操作。

1. 从 `develop` 更新本地代码。
2. 创建 `feature/<name>` 分支。
3. 在功能分支完成开发和测试。
4. 提交 Pull Request 或 Merge Request 到 `develop`。

示例命令如下。

```bash
git checkout develop
git pull
git checkout -b feature/query-audit-improvements
```

## 发布流程

如果你准备发版，必须通过 `release/vX.Y.Z` 分支收口，不要直接把
`develop` 合并到 `main`。

1. 从 `develop` 创建 `release/vX.Y.Z`。
2. 在 `release` 分支完成版本号调整、最终测试和发布修复。
3. 先 push `release/vX.Y.Z` 分支，再为同一提交创建 `vX.Y.Z` tag。
4. 由 GitHub Actions 自动完成 PyPI 发布和 GitHub Release 更新。
5. 发布成功后，自动创建回合并到 `main` 和 `develop` 的 PR。

示例命令如下。

```bash
git checkout develop
git pull
git checkout -b release/v1.2.0
```

发布触发和同步步骤如下。这里保留分支命名和版本标签的固定格式，便于自动化
校验分支、tag 和 `pyproject.toml` 版本号是否一致。

```bash
git checkout release/v1.2.0
git push origin release/v1.2.0
git tag -a v1.2.0 -m "Release version 1.2.0"
git push origin v1.2.0
```

随后由 GitHub Actions 自动发布到 PyPI、更新 GitHub Release，并创建回合并
到 `main` 和 `develop` 的 Pull Request。分支同步通过 PR 完成，不再使用这里
的手工 merge 命令作为正式发布路径。

## 紧急修复流程

如果线上已经出问题，需要快速修复，必须从 `main` 创建 `hotfix` 分支，避免
把未发布的 `develop` 代码一起带进生产。

1. 从 `main` 创建 `hotfix/<issue-id>`。
2. 在 `hotfix` 分支完成修复和验证。
3. 合并回 `main` 并发布。
4. 再把相同修复同步回 `develop`。

示例分支名如下。

- `hotfix/TICKET-101`
- `hotfix/login-timeout`

## 客户定制化需求

客户定制化是最容易把主仓库拖入长期分叉的区域，因此要优先约束实现方式。

### 推荐方案：通过架构解耦

如果需求可以参数化、开关化或模块化，优先用这些方式处理，而不是创建长期客
户分支。

- 用配置文件承载 Logo、主题色、API 地址、开关参数
- 用插件或模块化接口承载差异功能
- 用 feature flags 控制客户差异行为

这类客户代码更适合放在独立仓库，部署时与主产品构建物组合。

### 临时方案：客户长期分支

只有在改动极小、无法解耦时，才考虑长期客户分支。

| Rule | Requirement |
| --- | --- |
| Branch name | `customer/<customer-name>` |
| Start point | 必须从明确的版本 tag 创建 |
| Upgrade path | 后续从新的主线版本 tag 合并升级 |

正确示例如下。

```bash
git checkout -b customer/client-a v1.2.0
```

后续升级示例如下。

```bash
git checkout customer/client-a
git merge v1.3.0
git merge-base customer/client-a v1.3.0
```

## 版本号和标签

版本标签是生产状态的唯一追踪点，因此必须保持清晰、一致、可回溯。

### 主产品版本

主产品版本遵循语义化版本规范，格式为 `vMAJOR.MINOR.PATCH`，例如
`v2.1.0`。

规则如下。

- `main` 上的每次正式发布都必须打唯一 tag
- 生产环境构建物应和 `main` 上的发布 tag 一一对应

### 客户版本

客户版本不能直接复用主产品版本号，否则无法清楚追踪来源。

推荐格式如下。

```text
<主线版本号>-<客户标识>.<迭代号>
```

示例如下。

- `v2.1.0-clientA.0`
- `v2.1.0-clientA.1`
- `v2.2.0-clientA.0`

## AI 工具协作要求

AI 工具在本仓库中执行 Git 操作时，必须遵守和人工开发相同的边界，而且要更
保守。

- 在创建分支、提交、合并、推送前先检查仓库状态
- 不直接向 `main` push 代码
- 优先使用分支加 PR 或 MR
- 不改写已发布历史，除非用户明确要求且风险已确认
- 不对受保护分支执行 force push

`AGENT.md` 是给 AI 协作工具的补充约束，与本文档一起生效。

## 常见误区

这些做法会破坏分支模型或提高发布风险，应该避免。

- 直接在 `main` 上开发功能
- 让 `hotfix` 从 `develop` 分出
- 发布后只合并到 `main`，忘记回合并 `develop`
- 为客户需求直接长期修改主干代码

## Next steps

如果你要在这个仓库里协作开发，建议继续阅读 `AGENT.md`，确认 AI 协作规
则和本规范一致。
