# 发布自动化与 PyPI 分发设计

本文定义 `sql-query-mcp` 的标准化发布方案。目标是让项目从“需要手动
clone 仓库并本地安装”升级为“可以通过 PyPI 直接安装，并在 GitHub 上保留
清晰、可回溯的 release 记录”。

本设计采用与你当前仓库一致的 Git Flow 方向：开发改动先进入 `develop`，
发布准备在 `release/vX.Y.Z` 上收口，正式发布由 `vX.Y.Z` tag 触发自动化流
水线。发布成功后，系统自动创建回合并 PR，把已发布代码同步到 `main` 和
`develop`。

这里也明确收口当前仓库的 release 分支命名：后续统一采用 `release/vX.Y.Z`。
这不是引入新的分支模型，而是把仓库中已经实际使用的带 `v` 命名方式正式写
成规则，并同步反映到 Git workflow 文档和自动化实现中。

## 背景

仓库当前已经具备 Python 包的基本结构。`pyproject.toml` 已声明项目名、版
本号、依赖和 CLI 入口，说明这个项目已经接近一个可分发的 Python package。
但从开源使用体验来看，还有几处明显缺口。

- 当前 `README.md` 还没有统一为面向最终用户的 `pipx` 接入路径。
- 仓库还没有 GitHub Actions workflow，发布流程主要依赖人工操作。
- 虽然 Git 规范已经定义了 `release/<version>` 和 tag 规则，但它们还没有和
  PyPI、GitHub Release 建立可靠的自动化联动。
- 仓库对外已经开源，但用户还缺少统一、清晰的 PyPI 接入说明。

这会带来三个问题：首次使用门槛偏高、版本产物不够标准化，以及线上可回溯
的 release 记录不够完整。

## 实施前置检查

在进入实现前，需要先确认 PyPI 分发名本身可用，并且与你计划公开给用户的
安装命令一致。否则 workflow、README 和 GitHub Release 都可能围绕一个无法
使用的分发名展开。

前置检查包括：

- 确认 `sql-query-mcp` 这个 PyPI distribution name 可注册或已由当前项目持有。
- 确认用户接入说明继续采用 `pipx install sql-query-mcp` 和
  `pipx run --spec sql-query-mcp sql-query-mcp`。
- 确认 package import 路径 `sql_query_mcp` 与 distribution name 的差异在文
  档中表达清楚。

如果 PyPI 名称不可用，则需要先调整分发名，再继续实现自动发布方案。

## 目标

这次工作聚焦在建立一个可长期复用的正式发布链路。设计完成后，仓库需要具
备清晰的版本来源、稳定的构建流程，以及面向用户的标准安装方式。

- 让用户可以通过 `pipx install sql-query-mcp` 或
  `pipx run --spec sql-query-mcp sql-query-mcp` 接入项目。
- 让 `vX.Y.Z` tag、GitHub Release、PyPI 版本三者保持一一对应。
- 保持 `release/vX.Y.Z` 作为发布收口分支，符合现有 Git 规范。
- 在发布成功后自动创建回合并 PR，而不是直接改写受保护分支。
- 把发布失败与分支同步解耦，避免未成功发布的代码进入 `main`。
- 在仓库中补齐发布所需的文档、CI 校验和凭证使用约定。

## 非目标

这次工作不会把版本治理做成全自动语义化发版平台，也不会引入超出当前仓库
规模的复杂工具链。

- 不引入自动计算版本号的 release bot。
- 不实现自动 merge 到 `main` 或 `develop`。
- 不在第一版引入 `CHANGELOG.md` 的强制生成机制。
- 不切换到新的 Python 打包后端，只在现有 `setuptools` 基础上完善配置。
- 不改变 `sql-query-mcp` 的运行时行为或 MCP tool surface。
- 不在第一版把 `hotfix/*` 发布也接入同一套自动化。

## 方案概述

发布链路采用“tag 驱动的自动发布 + 自动创建回合并 PR”的模型。准备发版
时，团队仍然在 `release/vX.Y.Z` 分支上完成版本调整、文档同步和最终测试。
当分支确认可发布后，在该分支的发布提交上创建 `vX.Y.Z` tag，并 push 到远
端。

GitHub Actions 监听 `v*` tag。workflow 首先校验 tag 与 `pyproject.toml`
中的 `project.version` 是否完全一致，然后执行测试、构建 `sdist` 和 `wheel`
包、上传正式 PyPI、创建 GitHub Release。只有当前面的发布动作全部成功后，
才继续创建两个 PR：

- `release/vX.Y.Z -> main`
- `release/vX.Y.Z -> develop`

这两个 PR 用于同步已发布代码，而不是替代发布动作本身。这样可以让 `main`
保持“已成功发布代码的备份分支”定位，同时保留团队现有的 PR 审核边界。

## 发布流程

这一节定义发布链路在日常使用中的顺序和责任边界。流程中的每一步都需要明
确输入和输出，避免出现“tag 已打，但包没发布”或“包已发布，但主分支没同
步”的状态漂移。

1. 从 `develop` 创建 `release/vX.Y.Z`。
2. 在 `release/vX.Y.Z` 上调整 `pyproject.toml` 版本号，并同步更新需要反映
   版本变化的文档。
3. 在 `release/vX.Y.Z` 上完成最终测试和发布前检查。
4. 在发布提交上创建 `vX.Y.Z` tag，并 push 对应 branch 和 tag。
5. GitHub Actions 自动执行发布 workflow。
6. 如果测试、构建、上传 PyPI、创建 GitHub Release 全部成功，则自动创建
   回合并 PR。
7. 团队审核并合并 `release/vX.Y.Z -> main` 和 `release/vX.Y.Z -> develop`
   的 PR，完成分支同步。

这里有一个重要约束：回合并 PR 的创建依赖发布成功，而不是单纯依赖 tag 存
在。只要正式发布没有成功，`main` 就不接收对应代码。

为了降低 tag 触发时拿不到 release 分支的概率，操作顺序需要固定为：先 push
`release/vX.Y.Z` 分支，再 push `vX.Y.Z` tag。workflow 仍然要对分支发现做短
暂重试，但这个顺序是团队默认操作规范。

## 仓库变更设计

这一节定义仓库里需要补齐的主要文件和职责边界。目标不是一口气引入很多发
布工具，而是把发布职责拆到最小且可维护的几个文件中。

### `.github/workflows/ci.yml`

这个 workflow 负责持续验证，服务对象是 `feature/*`、`develop`、
`release/*`、`main` 和 Pull Request。它的目标是尽量在正式打 tag 之前发现
问题，并在 release PR 合并到 `main` 之后继续验证主分支状态。

建议职责如下：

- 安装项目及依赖。
- 运行现有测试命令。
- 执行基本打包检查，确认项目可以正常构建。

### `.github/workflows/release.yml`

这个 workflow 负责正式发布。它监听 `v*` tag，并串行完成版本校验、测试、
构建、PyPI 上传、GitHub Release 创建，以及回合并 PR 创建。

它还必须配置 workflow 级别的 concurrency，并以 tag 作为并发键，确保同一
个 `vX.Y.Z` 在任意时刻只会有一个正式发布任务执行。这样可以避免重复上传
PyPI、重复创建 GitHub Release，或在补偿执行时产生竞态。

建议包含以下阶段：

1. 解析 tag，例如 `v0.2.0`。
2. 获取远端 `release/vX.Y.Z` 分支引用，并确认它在远端存在。
3. 从仓库读取 `pyproject.toml` 中的 `project.version`。
4. 校验 tag 去掉前缀 `v` 后是否与项目版本一致。
5. 校验当前 tag 指向的提交可从远端 `release/vX.Y.Z` 分支到达。
6. 运行测试。
7. 构建 `sdist` 和 `wheel`。
8. 执行发布前校验，例如 `twine check`、从构建出的 wheel 安装并做 CLI
   smoke test。
9. 上传到正式 PyPI。
10. 创建 GitHub Release，并把构建产物作为附件。
11. 自动创建 `release/vX.Y.Z -> main` 与 `release/vX.Y.Z -> develop` 的 PR。

### `pyproject.toml`

这个文件继续作为版本号和包元数据的唯一来源。Git tag 是对该版本的外部标
识，而不是新的版本事实来源。所有发布前检查都以这里的版本值为准。

在现有基础上，建议补齐以下信息：

- 更完整的 license 声明。
- 作者或维护者信息。
- 更准确的 classifiers。
- 对 PyPI 展示更友好的项目元数据。

### `README.md`

主 `README.md` 需要把安装入口改成面向最终用户的分发路径。当前把 clone 仓
库作为第一入口，不利于开源用户快速试用，也无法体现 PyPI 分发价值。

建议调整为：

- Quick start 提供 `pipx install` 和 `pipx run` 两种正式接入方式。
- 保留本地 clone + editable install 作为开发者路径。
- 补充 GitHub Release 和版本安装的简单说明。

### 发布说明文档

仓库还需要一份独立的发布文档，例如 `docs/release-process.md`。它负责说明
团队如何准备 release branch、何时打 tag、需要配置哪些 secrets，以及如果
发布失败该怎么处理。

这份文档不重复 Git branch 基础规则，而是专注回答“这个仓库具体怎么发版”。

它还需要明确列出受影响的协作文档，例如 `docs/git-workflow.md`，确保其中的
release 分支命名示例同步为 `release/vX.Y.Z`。

## 版本与分支规则

自动发布的前提是版本号、分支名和 tag 命名保持一致。这样可以让 workflow
在机器层面做硬校验，而不是依赖人工记忆。

- release 分支格式固定为 `release/vX.Y.Z`。
- Git tag 格式固定为 `vX.Y.Z`。
- `pyproject.toml` 中的 `project.version` 固定为 `X.Y.Z`。

发布 workflow 需要显式验证以下关系：

- 当前 tag 是否以 `v` 开头。
- tag 版本与 `project.version` 是否一致。
- tag 所在提交是否可从对应 `release/vX.Y.Z` 分支解析到。

如果这三者之一不成立，workflow 必须失败并停止发布。这样可以防止有人在错
误分支上误打 tag，或者 tag 与包版本不一致。

为了让这个校验可以真正落地，workflow 需要在 tag 触发后显式 fetch 对应的
`release/vX.Y.Z` 远端引用。如果远端不存在该分支，或者无法证明 tagged
commit 来自该分支，workflow 必须失败，并给出明确错误信息。

考虑到 branch 和 tag push 之间可能存在短暂时序差，workflow 可以在读取远端
`release/vX.Y.Z` 时做有限次重试。例如重试几次并带短间隔等待。如果重试后仍
无法解析分支，则认定为失败，而不是继续发布。

## develop 版本管理规则

回合并到 `develop` 时，最容易产生歧义的是 `pyproject.toml` 的版本号状态。
如果这件事不先定清楚，自动创建 PR 之后很容易在合并阶段发生版本回退争议。

第一版建议采用简单且稳定的规则：

- `release/vX.Y.Z` 在发版前持有正式版本 `X.Y.Z`。
- `main` 合并 release 后保持 `X.Y.Z`，作为已发布版本归档。
- `develop` 在 release 回合并完成后，不要求自动立即升到下一个版本。
- 下一次准备发版时，再从当前 `develop` 创建新的 `release/vA.B.C`，并在那
  个 release 分支上调整正式版本号。

这条规则的核心目的是避免把“下一版本规划”耦合进本次发布自动化。后续如果
你想采用 `develop` 永远领先一个版本的策略，可以作为单独迭代再设计。

## GitHub Actions 权限与凭证

自动发布需要最小但明确的仓库权限。凭证设计的目标是让发布链路可运行，同
时避免把长期密钥散落到代码仓库中。

建议使用以下配置：

- 仓库 secret：`PYPI_API_TOKEN`
- workflow permissions：`contents: write`、`pull-requests: write`
- 如果使用 `gh` CLI 或 GitHub API 创建 PR，则使用 Actions 提供的
  `GITHUB_TOKEN`

PyPI token 只用于上传包，不在任何文档示例中明文展示。文档只说明配置位置
和权限要求，不记录真实值。

## 错误处理与失败边界

发布自动化必须优先保证“失败即停止”，而不是尽量继续执行。对于分发系统来
说，半成功状态比完全失败更难处理。

需要明确以下规则：

- 如果版本校验失败，workflow 立即结束，不运行测试和上传。
- 如果测试或构建失败，workflow 不上传 PyPI，不创建 Release，不创建 PR。
- 如果 PyPI 上传失败，workflow 不创建回合并 PR。
- 如果 GitHub Release 创建失败，workflow 也不创建回合并 PR。
- 如果发布已经成功，但 PR 创建失败，workflow 需要明确报错，并把这类问题
  视为“发布后同步失败”，由维护者手工补建 PR。

这个边界的核心原则是：只有在“包已经成功对外发布”之后，才允许开始主干
同步动作。

还需要单独处理“部分成功”的恢复路径。PyPI 上的版本天然不可覆盖，所以如
果已经上传成功，但后续 GitHub Release 或 PR 创建失败，维护者不能简单重跑
整个发布并期待得到同样结果。

建议恢复策略如下：

- 把“PyPI 已成功发布”视为正式发布已经成立。
- 如果后续步骤失败，优先进入补偿流程，而不是重新上传同一版本。
- release workflow 明确采用“同一 workflow 内检测已发布版本并跳过重复上传”
  的恢复模型。
- 当 workflow 重跑时，如果检测到目标版本已经存在于 PyPI，则把发布步骤视为
  已完成，并继续执行 GitHub Release 补建或 PR 补建逻辑。
- 文档必须提供人工恢复步骤，例如手工创建 GitHub Release、手工补建回合并
  PR、检查 tag 与分支状态。

这样可以避免在 PyPI 已经存在目标版本时，维护者因为重复上传而卡在不可恢
复的错误状态。

为了避免把“PyPI 上已经有这个版本”误判成任意场景下都安全，workflow 还需
要把这条恢复路径限制在同一个 tag 的补偿执行上。也就是说，只有当维护者已
确认同一个 `vX.Y.Z` tag 之前已经成功上传过正确版本，后续重跑才允许跳过
PyPI 上传，进入 GitHub Release 或 PR 的补偿步骤。

第一版不要求 workflow 去证明 PyPI 上现有文件与当前 commit 的二进制完全等
价，而是把这类判断留给维护者确认，并在发布文档中写清楚这个人工检查边界。

## 测试与验证策略

第一版发布自动化不需要引入复杂矩阵，但需要覆盖最关键的正确性检查。目的
是保证包能装、测试能过、元数据可信。

建议最少包含以下验证：

- 运行现有单元测试。
- 执行标准构建命令，产出 `dist/*.tar.gz` 和 `dist/*.whl`。
- 对构建结果执行 `twine check`，确认元数据和 long description 合法。
- 在 fresh virtualenv 中从构建出的 wheel 执行一次安装验证，而不是只确认文
  件存在。
- 对安装后的 CLI 执行 `sql-query-mcp --help` 作为最小 smoke test，确认入口
  可以被解析。

如果后续需要提高可信度，可以再追加 Python 多版本矩阵，但不作为这次设计
的必选项。

## GitHub Release 内容策略

GitHub Release 既是用户查看版本记录的入口，也是排查线上版本来源的关键节
点。因此第一版就需要具备可读性，但不必过度追求复杂模板。

建议策略如下：

- title 使用 `vX.Y.Z`
- 附件包含 `sdist` 和 `wheel`
- body 优先使用自动生成的 release notes
- body 额外补充一个固定安装示例：`pipx install 'sql-query-mcp==X.Y.Z'`
- 创建逻辑采用 create-or-update：如果 release 已存在，则补齐缺失的 notes
  或 assets，而不是直接失败

这样可以先建立清晰的版本归档能力，后续如果你决定维护 changelog，再升级
到自定义 release notes 模板。

## 回合并 PR 策略

发布成功后自动创建回合并 PR，是为了把“已对外发布”的事实同步回长期分支。
但 `develop` 往往会比 release 分支继续前进，所以这里需要明确边界，避免把
自动化假设成总能无冲突完成。

建议规则如下：

- `release/vX.Y.Z -> main` 是必建 PR，因为 `main` 承担已发布代码的归档角色。
- `release/vX.Y.Z -> develop` 也应自动尝试创建，用于回合并 release 阶段产生
  的版本调整和发布修复。
- PR 创建逻辑必须具备幂等性。如果目标 PR 已存在，workflow 记录并复用该结
  果，而不是报错退出。
- 如果 `develop` 已前进但仍可创建 PR，则保留 PR 让维护者正常审查与合并。
- 如果 `develop` 上没有差异，允许 PR 不创建，并把结果记录为“无需回合并”。
- 如果因为分支冲突或 API 限制无法创建 PR，workflow 需要明确报错，并要求维
  护者手工处理冲突后再补建 PR。

这个策略的重点不是强求自动化覆盖所有 merge 场景，而是让“自动尝试、失败
可恢复、结果可见”成为默认行为。

为了让这部分实现可操作，针对 `develop` 需要进一步采用以下判定顺序：

1. 先查询是否已存在同一 source 和 target 的 open PR；如果存在，则复用并记
   录结果。
2. 如果不存在 open PR，则比较 `release/vX.Y.Z` 与 `develop` 的差异。
3. 如果 release 分支相对 `develop` 没有新增提交，记录为“无需回合并”，不创
   建 PR。
4. 如果存在可提交的差异，则创建 PR。
5. 如果比较或创建 PR 的过程中遇到 GitHub API 限制、分支异常或需要人工处
   理的冲突信号，则 workflow 失败并提示维护者手工补建。

这里的目标不是在 CI 中自动解决 merge conflict，而是把“已有 PR”“无需 PR”
“可自动建 PR”“必须人工介入”这四种状态区分清楚。

## 风险与缓解

这个方案的主要风险不在 Python 打包本身，而在自动化边界是否清晰。只有边界
足够清楚，自动化才会降低成本，而不是制造新的排查负担。

- 风险一：tag 与版本号不一致，导致错误版本被发布。缓解方式是把版本一致性
  校验做成 workflow 的第一步。
- 风险二：发布成功但主干未同步。缓解方式是把回合并 PR 自动创建纳入发布
  workflow，并对失败给出明确告警。
- 风险三：主分支被 workflow 直接改写。缓解方式是只创建 PR，不做自动 merge。
- 风险四：README 仍然把本地 clone 当成主安装路径。缓解方式是调整 README，
  让 PyPI 安装成为默认入口。
- 风险五：凭证管理不清晰。缓解方式是把 PyPI token 严格限制在 GitHub
  secrets 中使用。

## 实施范围建议

为了把第一版控制在高价值、低复杂度的范围内，实施阶段建议只覆盖这几类改
动：发布 workflow、CI workflow、`pyproject.toml` 元数据补齐、README 安装
说明调整，以及新增发布流程文档。

像自动 changelog、TestPyPI 演练通道、多 Python 版本矩阵、自动语义化发版
等增强项，可以放到后续迭代，而不是在第一版一起引入。

## v1 必选项与后续增强项

为了避免实施阶段把 hardening 想法和第一版必交付混在一起，这里把范围再明
确拆成两层。

v1 必选项：

- 新增 `ci.yml` 与 `release.yml`
- 基于 tag 的版本一致性校验与 release 分支可达性校验
- `release.yml` 的 concurrency 控制
- 单元测试、构建、`twine check`、fresh virtualenv 安装 wheel、
  `sql-query-mcp --help` smoke test
- 上传正式 PyPI
- GitHub Release 的 create-or-update 行为
- `main` 与 `develop` 的回合并 PR 自动创建或跳过判定
- `pyproject.toml` 元数据补齐
- `README.md` 安装路径更新
- 新增发布流程文档

后续增强项：

- 自动 changelog 管理
- TestPyPI 演练通道
- 多 Python 版本矩阵
- 更强的发布补偿自动化
- hotfix 分支的独立自动发布链路

## 范围边界说明

为了保证第一版可落地，这次自动化明确只覆盖标准 release 分支发版路径：
`develop -> release/vX.Y.Z -> vX.Y.Z tag -> 自动发布 -> 回合并 PR`。

`hotfix/*` 分支依然保留在 Git 规范中，但暂时不接入这套 PyPI 自动发布流
程。等标准 release 流程稳定后，再单独设计 hotfix 发版自动化，避免在第一
版就把两套分支路径耦合到同一个 workflow 中。

## 下一步

在本设计确认并完成 review 后，下一阶段应编写 implementation plan，把需
要修改的 workflow、文档和项目元数据拆成可执行步骤，再开始实际实现。
