# Repository polish and Awesome MCP submission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `sql-query-mcp` presentation-ready for external discovery and community contributions, then prepare accurate submission copy for `awesome-mcp-servers`.

**Architecture:** Keep runtime behavior unchanged and focus on repository surface area. Use an English-first `README.md` as the external landing page, add a Chinese documentation entry point, add contribution and roadmap docs, verify `docs/git-workflow.md` against Git Flow-adjacent best practices, and align package metadata and license details with the new public-facing positioning.

**Tech Stack:** Markdown docs, MIT license text, Python packaging metadata in `pyproject.toml`, existing `unittest` test suite, GitHub repository conventions.

---

## File map

- `README.md`
  - Main English-first landing page for external users.
- `docs/README.zh-CN.md`
  - Chinese documentation entry point for existing Chinese-speaking users.
- `CONTRIBUTING.md`
  - Public contribution entry point that links to `docs/git-workflow.md`.
- `docs/roadmap.md`
  - Current support, candidate adapters, and contribution opportunities.
- `docs/adapter-development.md`
  - Practical guide for adding a new database adapter.
- `docs/git-workflow.md`
  - Source-of-truth Git workflow doc, revised only if concrete inconsistencies or risky examples are found.
- `LICENSE`
  - MIT license text.
- `pyproject.toml`
  - Package metadata aligned with the new public-facing documentation.
- `.github/ISSUE_TEMPLATE/bug_report.md`
  - Bug report template for external users.
- `.github/ISSUE_TEMPLATE/feature_request.md`
  - Feature request template for adapter requests and roadmap input.

## Task 1: Audit public claims and implementation boundaries

**Files:**
- Read: `README.md`
- Read: `docs/project-overview.md`
- Read: `docs/api-reference.md`
- Read: `docs/git-workflow.md`
- Read: `pyproject.toml`
- Read: `sql_query_mcp/app.py`
- Read: `sql_query_mcp/validator.py`
- Read: `sql_query_mcp/registry.py`
- Test: `tests/test_validator.py`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Re-read the source-of-truth implementation files**

Confirm the exact current claims that public docs may make:

```text
Current support: PostgreSQL, MySQL
Core safety claims: read-only validation, AST-based parsing, explicit engine handling, audit logging
```

- [ ] **Step 2: Write a short claim checklist in your scratch notes**

Use this checklist while editing docs:

```text
- Do not claim support beyond PostgreSQL/MySQL
- Do not imply write capabilities
- Do not imply generic DB support is already shipped
- Keep future adapters labeled as candidate/community direction
```

- [ ] **Step 3: Run the current test suite before doc edits**

Run: `PYTHONPATH=. python3 -m unittest discover -s tests`
Expected: all existing tests pass

- [ ] **Step 4: Record any existing documentation mismatches**

Focus on mismatches that will affect the new README, roadmap, and contribution
docs.

- [ ] **Step 5: Commit the audit checkpoint if you created any helper notes in tracked files**

```bash
git add <only-if-tracked-files-were-added>
git commit -m "docs: add repo polish planning notes"
```

If no tracked files changed, skip this commit.

## Task 2: Rewrite `README.md` as the English-first landing page

**Files:**
- Modify: `README.md`
- Read: `docs/project-overview.md`
- Read: `docs/api-reference.md`
- Read: `docs/codex-setup.md`
- Read: `docs/opencode-setup.md`

- [ ] **Step 1: Replace the title and opening section with English-first positioning**

Use copy shaped like this:

```md
# sql-query-mcp

Read-only SQL MCP server for AI assistants. It currently supports PostgreSQL
and MySQL, with an adapter-oriented path toward more database engines.
```

- [ ] **Step 2: Add a quick-start section that stays implementation-accurate**

Keep the installation and configuration path short:

```md
## Quick start

1. Choose `pipx install sql-query-mcp` or `pipx run --spec sql-query-mcp sql-query-mcp`.
2. Save a config file outside the repository.
3. Put `SQL_QUERY_MCP_CONFIG` and real DSNs in the MCP client's environment block.
4. Register the server in your MCP client.
```

- [ ] **Step 3: Add a capability section with current tools only**

Summarize only the existing MCP tools and engines already implemented.

- [ ] **Step 4: Add a safety section with verifiable claims only**

Include only claims backed by current code and docs:

```md
- Explicit engine configuration
- Read-only SQL validation with `sqlglot`
- Engine-specific namespace handling
- Audit logging
```

- [ ] **Step 5: Add documentation, roadmap, and contributing links**

Link to:

```md
- `docs/README.zh-CN.md`
- `docs/project-overview.md`
- `docs/api-reference.md`
- `docs/roadmap.md`
- `CONTRIBUTING.md`
```

- [ ] **Step 6: Add a short license section**

```md
## License

MIT
```

- [ ] **Step 7: Re-read the final README for tone and scope control**

Check that future direction never reads like shipped support.

- [ ] **Step 8: Commit the README rewrite**

```bash
git add README.md
git commit -m "docs: rewrite README for external users"
```

## Task 3: Add the Chinese documentation entry point

**Files:**
- Create: `docs/README.zh-CN.md`
- Read: `README.md`
- Read: `docs/project-overview.md`
- Read: `docs/api-reference.md`

- [ ] **Step 1: Create `docs/README.zh-CN.md` with a short Chinese overview**

Include:

```md
# sql-query-mcp 中文说明

`sql-query-mcp` 是一个面向 AI 助手的只读 SQL MCP 服务。
主 README 采用英文优先，本文提供中文入口。
```

- [ ] **Step 2: Link Chinese readers to the most relevant docs**

At minimum include:

```md
- `README.md`
- `docs/project-overview.md`
- `docs/api-reference.md`
- `docs/codex-setup.md`
- `docs/opencode-setup.md`
```

- [ ] **Step 3: Add a short note about current support and future direction**

Use wording that separates:

```text
当前支持: PostgreSQL / MySQL
未来方向: 候选 adapters，不代表已支持
```

- [ ] **Step 4: Self-review for concise Chinese wording**

Keep it as an entry page, not a second full README.

- [ ] **Step 5: Commit the Chinese entry doc**

```bash
git add docs/README.zh-CN.md
git commit -m "docs: add Chinese documentation entry"
```

## Task 4: Add contribution guidance that points to `docs/git-workflow.md`

**Files:**
- Create: `CONTRIBUTING.md`
- Read: `docs/git-workflow.md`
- Read: `AGENT.md`
- Read: `README.md`

- [ ] **Step 1: Create the opening section and contribution scope**

Start with:

```md
# Contributing

This repository welcomes documentation improvements, bug fixes, and new
database adapter contributions.
```

- [ ] **Step 2: Add issue and pull request guidance**

Cover:

```md
- Open an issue for significant changes
- Keep changes focused
- Update docs when behavior changes
- Run the relevant tests before submitting a PR
```

- [ ] **Step 3: Add the Git workflow source-of-truth rule**

Use explicit wording like:

```md
The authoritative Git workflow for this repository is documented in
`docs/git-workflow.md`.
```

- [ ] **Step 4: Add a short section for new database adapter contributions**

Link contributors to `docs/adapter-development.md` and `docs/roadmap.md`.

- [ ] **Step 5: Add the test command used by this repository**

```bash
PYTHONPATH=. python3 -m unittest discover -s tests
```

- [ ] **Step 6: Re-read the file to confirm it references, not duplicates, Git rules**

Do not repeat detailed branch strategy, release flow, or hotfix flow.

- [ ] **Step 7: Commit the contribution guide**

```bash
git add CONTRIBUTING.md
git commit -m "docs: add contribution guide"
```

## Task 5: Add roadmap and adapter contribution docs

**Files:**
- Create: `docs/roadmap.md`
- Create: `docs/adapter-development.md`
- Read: `docs/project-overview.md`
- Read: `docs/api-reference.md`
- Read: `sql_query_mcp/adapters/postgres.py`
- Read: `sql_query_mcp/adapters/mysql.py`
- Read: `tests/test_metadata.py`
- Read: `tests/test_executor.py`

- [ ] **Step 1: Create `docs/roadmap.md` with support taxonomy headings**

Use sections shaped like this:

```md
## Supported now
## Candidate adapters
## Open for contribution
```

- [ ] **Step 2: Fill `docs/roadmap.md` with accurate current support**

Current support must only mention PostgreSQL and MySQL.

- [ ] **Step 3: Add candidate adapter direction without promising delivery**

Use wording like:

```text
Candidate adapters may include SQLite, SQL Server, or ClickHouse, but they are
not officially supported until implemented, tested, and documented.
```

- [ ] **Step 4: Create `docs/adapter-development.md` with the adapter boundary**

Explain where adapters live and what they interact with:

```text
sql_query_mcp/adapters/
sql_query_mcp/registry.py
sql_query_mcp/introspection.py
sql_query_mcp/executor.py
```

- [ ] **Step 5: Add minimum expectations for a new adapter**

Cover areas such as connection handling, metadata inspection, query execution,
namespace behavior, and tests.

- [ ] **Step 6: Link both docs back to `CONTRIBUTING.md` and `docs/git-workflow.md` where appropriate**

Keep Git policy centralized.

- [ ] **Step 7: Commit roadmap and adapter docs**

```bash
git add docs/roadmap.md docs/adapter-development.md
git commit -m "docs: add roadmap and adapter guide"
```

## Task 6: Add MIT license and align package metadata

**Files:**
- Create: `LICENSE`
- Modify: `pyproject.toml`
- Read: `README.md`

- [ ] **Step 1: Add the standard MIT license text to `LICENSE`**

Use the standard MIT template with the correct copyright holder.

- [ ] **Step 2: Update `pyproject.toml` metadata to reflect the license**

Add or adjust metadata such as:

```toml
[project]
license = { text = "MIT" }

classifiers = [
  "License :: OSI Approved :: MIT License",
]
```

- [ ] **Step 3: Verify the package description still matches the public README positioning**

Keep the description aligned with current support.

- [ ] **Step 4: Run a lightweight packaging validation step**

Run one of the following, depending on the available tooling:

```bash
python3 -m build
```

Expected: build metadata resolves successfully

If `build` is not installed and you do not want to add tooling, use a minimal
syntax validation path that confirms `pyproject.toml` remains valid.

- [ ] **Step 5: Commit the license and metadata changes**

```bash
git add LICENSE pyproject.toml
git commit -m "chore: add MIT license metadata"
```

## Task 7: Review and minimally fix `docs/git-workflow.md`

**Files:**
- Modify: `docs/git-workflow.md`
- Read: `AGENT.md`
- Read: `CONTRIBUTING.md`

- [ ] **Step 1: Compare the current workflow doc against the approved scope**

Check for concrete issues only:

```text
- rule/example mismatch
- ambiguous release handling
- ambiguous hotfix handling
- advice that conflicts with PR-first expectations
```

- [ ] **Step 2: Fix the `main` rule/example consistency if needed**

If the doc says `main` should not be directly pushed to, adjust examples or
clarify that merges happen via protected-branch workflow rather than normal
direct development.

- [ ] **Step 3: Clarify hotfix synchronization when an active `release/*` branch exists**

Add a brief note only if needed. Keep it minimal and specific.

- [ ] **Step 4: Add short advisory notes for branch protection or CI only if they reduce ambiguity**

Do not redesign repository governance.

- [ ] **Step 5: Re-read the full file to confirm it is still your repo-specific workflow, not a generic template**

- [ ] **Step 6: Commit the workflow doc changes if any were made**

```bash
git add docs/git-workflow.md
git commit -m "docs: refine git workflow guidance"
```

If no edits were needed, skip this commit and record that the doc was retained
as-is.

## Task 8: Optionally add lightweight GitHub issue templates

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug_report.md`
- Create: `.github/ISSUE_TEMPLATE/feature_request.md`
- Read: `docs/roadmap.md`
- Read: `CONTRIBUTING.md`

- [ ] **Step 1: Decide whether to include issue templates in this pass**

Include them only if the main documentation tasks are already complete and the
scope remains small. If not, skip this task without blocking the rest of the
plan.

- [ ] **Step 2: Create a bug report template**

Include fields for environment, MCP client, database engine, reproduction steps,
expected behavior, and actual behavior.

- [ ] **Step 3: Create a feature request template**

Include fields for use case, requested capability, target database engine, and
whether the request is for current support or a candidate adapter.

- [ ] **Step 4: Keep both templates aligned with the new support taxonomy**

Use terms like `Supported now` and `Candidate adapters` where useful.

- [ ] **Step 5: Commit the issue templates**

```bash
git add .github/ISSUE_TEMPLATE/bug_report.md .github/ISSUE_TEMPLATE/feature_request.md
git commit -m "docs: add issue templates"
```

If this task was skipped, do not create this commit.

## Task 9: Verify links, run tests, and prepare Awesome MCP copy

**Files:**
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/adapter-development.md`
- Modify: `docs/git-workflow.md`
- Read: `docs/superpowers/specs/2026-03-19-repo-polish-and-awesome-mcp-design.md`

- [ ] **Step 1: Check all internal links across modified docs**

Verify every referenced file exists and uses the final path in each edited or
newly created document:

```text
- README.md
- docs/README.zh-CN.md
- CONTRIBUTING.md
- docs/roadmap.md
- docs/adapter-development.md
- docs/git-workflow.md
```

Pay special attention to backlinks among `CONTRIBUTING.md`,
`docs/git-workflow.md`, `docs/README.zh-CN.md`, `docs/roadmap.md`, and
`docs/adapter-development.md`.

- [ ] **Step 2: Run the repository test suite again**

Run: `PYTHONPATH=. python3 -m unittest discover -s tests`
Expected: all tests pass

- [ ] **Step 3: Run a cross-doc consistency review**

Compare these artifacts side by side:

```text
- README.md
- docs/README.zh-CN.md
- CONTRIBUTING.md
- docs/roadmap.md
- Awesome MCP submission copy
```

Confirm they all preserve the same support boundary:

```text
- PostgreSQL/MySQL only for current support
- read-only only
- future adapters clearly labeled as not yet supported
```

- [ ] **Step 4: Draft the Awesome MCP entry line in a scratch note or final response**

Use copy shaped like this:

```md
- [andyWang1688/sql-query-mcp](https://github.com/andyWang1688/sql-query-mcp) 🐍 🏠 - Read-only SQL MCP server for AI assistants with schema inspection, read-only query execution, AST-based validation, and audit logging. Currently supports PostgreSQL and MySQL, with an adapter-oriented path toward more database engines.
```

- [ ] **Step 5: Draft the Awesome MCP PR body**

Keep it short and fact-based:

```md
## Summary
- Add `sql-query-mcp` to the Databases section
- Read-only SQL MCP server for AI assistants
- Current support: PostgreSQL and MySQL
```

- [ ] **Step 6: Re-read the draft submission copy against the codebase and final docs**

Remove any wording that overstates current support.

- [ ] **Step 7: Commit the final doc polish if verification required edits**

```bash
git add README.md CONTRIBUTING.md docs/roadmap.md docs/adapter-development.md docs/git-workflow.md pyproject.toml LICENSE docs/README.zh-CN.md
git commit -m "docs: finalize repo polish for external discovery"
```

If issue templates were created in Task 8, add them in the same commit:

```bash
git add .github/ISSUE_TEMPLATE/bug_report.md .github/ISSUE_TEMPLATE/feature_request.md
```

If there are no remaining changes after previous commits, skip this commit.
