
git使用规范
分支管理

1. 标准分支,必须要有的 
> main      对应生产环境已发布代码（不允许直接push代码，需要提交merge request）
> release   对应测试环境（不推荐直接push代码，建议提交merge request）
> develop   对应开发环境
> feature/xxx 新功能开发分支，基于develop 创建

2. 客户本地化部署分支
> roche-main
> roche-release
> roche-develop
> roche/feature/xxx



``
<span style="background: linear-gradient(to right, #ff9a9e, #fadFc4); padding: 5px; color: #3a3a3a;">以 Docker 镜像为中心的敏捷部署。</span>

<span style="background: linear-gradient(to right, #0f9a9e, #fad0c4); padding: 5px; color: #4a4a4a;">以 main 分支为中心的清晰、可靠的 Git 版本历史。</span>



## 1. 文档目的

为规范团队的 Git 使用流程，确保代码库的整洁、可追溯，并高效管理产品主线与客户定制化版本的迭代，特制定本规范。所有团队成员均需遵守本文档定义的流程与规则。

## 2. 核心分支策略

项目采用基于 [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/) 的简化分支模型，定义如下核心分支：

*   **`main`**: **生产分支**。
    *   必须始终保持稳定，其 `HEAD` 对应最新线上生产环境的版本。
    *   **禁止**直接在此分支上进行任何提交。
    *   所有提交必须来自 `release` 分支或 `hotfix` 分支的合并。

*   **`develop`**: **主开发分支**。
    *   作为所有新功能开发的集成基础。
    *   所有 `feature` 分支从此分出，并最终合并回此分支。

*   **`feature/*`**: **功能分支**。
    *   用于开发新功能。
    *   命名规范: `feature/<feature-name>`，例如 `feature/user-authentication`。
    *   从 `develop` 分支创建，完成开发后合并回 `develop` 分支。

*   **`release/*`**: **预发布分支**。
    *   用于准备新的生产版本。
    *   命名规范: `release/<version>`，例如 `release/v1.2.0`。
    *   从 `develop` 分支创建。在此分支上进行版本号更新、最终测试和 Bug 修复。

*   **`hotfix/*`**: **紧急修复分支**。
    *   用于紧急修复生产环境的 Bug。
    *   命名规范: `hotfix/<issue-id>`，例如 `hotfix/TICKET-101`。
    *   **必须**从 `main` 分支创建，修复完成后**必须**同时合并回 `main` 和 `develop` 分支。

## 3. 主产品发布流程规范

本流程旨在确保部署到生产环境的构建物与 `main` 分支的代码状态一一对应。

1.  **准备发布**:
    *   从 `develop` 分支创建 `release` 分支。
        ```bash
        git checkout develop
        git pull
        git checkout -b release/v1.2.0
        ```

2.  **版本稳定**:
    *   在 `release` 分支上进行版本号更新、最后测试和必要的 Bug 修复。
    *   此分支是触发 CI/CD 流程构建**生产候选版本**（如 Docker 镜像）的唯一入口。

3.  **部署上线**:
    *   将由 `release` 分支构建并测试通过的产物部署到生产环境。

4.  **发布完成 (关键步骤)**:
    *   **确认部署成功后**，必须执行以下步骤以同步代码库状态：
    *   **a. 合并到 `main` 并打上标签**:
        ```bash
        git checkout main
        git pull
        git merge --no-ff release/v1.2.0
        git tag -a v1.2.0 -m "Release version 1.2.0"
        git push
        git push --tags
        ```
    *   **b. 合并回 `develop`**:
        ```bash
        git checkout develop
        git pull
        git merge --no-ff release/v1.2.0
        git push
        ```
    *   **c. (可选) 删除 `release` 分支**:
        ```bash
        git branch -d release/v1.2.0
        ```

## 4. 客户定制化版本管理规范

### 4.1. 基本原则

**优先通过架构解耦，而非代码分支，来管理定制化需求。** 直接修改核心代码为客户创建长期分支，会造成后期版本升级时巨大的合并冲突和维护成本。

### 4.2. 推荐方案：架构解耦

对于所有客户的定制化需求，应优先采用以下方式实现：

*   **配置文件**: 将 Logo、主题色、API 端点、开关等易变内容参数化，通过配置文件加载。
*   **插件/模块化**: 为常见的定制场景（如认证、报表、UI）定义清晰的接口，将定制功能作为独立插件或模块开发。
*   **功能开关 (Feature Flags)**: 在代码中预埋特定功能，通过配置为不同客户开启或关闭。

此方案下，客户的定制化代码应存放在**独立的 Git 仓库**中，部署时与主产品构建物组合。

### 4.3. 临时方案：长期客户分支

**仅在定制化需求极少、改动极小，且无法通过架构解耦时，方可采用此方案。**

*   **分支命名**: `customer/<customer-name>`，例如 `customer/client-A`。
*   **创建流程**:
    1.  **必须**从一个明确的 `main` 分支版本标签创建客户分支。
        ```bash
        # 错误做法: git checkout -b customer/client-A main
        # 正确做法:
        git checkout -b customer/client-A v1.2.0
        ```
    2.  所有定制化开发在此分支上进行。

*   **升级流程**:
    1.  当主线发布新版（如 `v1.3.0`）后，将新版本标签合并到客户分支。
        ```bash
        git checkout customer/client-A
        git merge v1.3.0
        ```
    2.  **必须**手动解决所有合并冲突，并进行充分的回归测试。
    3.  **注意**: 升级前，使用 `git merge-base` 确认合并基点，有助于评估工作量。
        ```bash
        git merge-base customer/client-A v1.3.0
        ```

## 5. 版本号与标签规范

### 5.1. 主产品版本号

*   遵循 **[语义化版本 (Semantic Versioning 2.0.0)](https://semver.org/lang/zh-CN/)** 规范，格式为 `vMAJOR.MINOR.PATCH`。
*   `main` 分支上的每个发布版本**必须**对应一个唯一的版本标签。

### 5.2. 客户版本号

*   **严禁**将主产品的版本号直接用于客户版本。
*   客户版本**必须**采用以下**复合版本号**格式：
    > **`<主线版本号>-<客户标识>.<迭代号>`**

*   **示例**:
    *   `v2.1.0-clientA.0`: 基于主线 `v2.1.0` 为客户 A 做的第一个版本。
    *   `v2.1.0-clientA.1`: 为上一个版本提供了 Bug 修复。
    *   `v2.2.0-clientA.0`: 将客户 A 的版本从 `v2.1.0` 升级到了 `v2.2.0`。

*   **理由**: 复合版本号是唯一能清晰追溯客户代码来源、准确报告和定位 Bug、避免版本混淆的管理方式。所有为客户构建的产物（如 Docker 镜像），都必须使用此复合版本号作为标签。
