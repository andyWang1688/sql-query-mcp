# Release and PyPI automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production-ready release pipeline that publishes `sql-query-mcp`
to PyPI from `release/vX.Y.Z` tags, creates GitHub Releases, and opens the
back-merge PRs to `main` and `develop`.

**Architecture:** Keep the runtime MCP server behavior unchanged and add release
automation around the existing Python package. Put naming and version parsing in
a small testable Python helper module, use GitHub Actions for CI and tagged
release orchestration, and update repository docs so PyPI installation and the
new release flow become the source of truth.

**Tech Stack:** Python 3.10+, `unittest`, `setuptools`, `build`, `twine`,
`actionlint`, GitHub Actions, `gh` CLI in Actions runners, Markdown docs,
PyPI API token.

---

## File map

This file map locks down the implementation boundaries before any edits start.
The release pipeline stays small by keeping pure parsing logic in Python,
orchestration in workflow YAML, and operator guidance in docs.

- `sql_query_mcp/release_metadata.py`
  - New helper module for parsing `vX.Y.Z` tags, deriving
    `release/vX.Y.Z`, reading `pyproject.toml`, resolving the effective release
    tag in normal and recovery runs, and exposing a small CLI for
    workflow-friendly outputs.
- `tests/test_release_metadata.py`
  - Unit tests for version parsing, branch naming, and CLI output from the new
    helper module.
- `pyproject.toml`
  - Package metadata for PyPI, including license and author details, plus any
    packaging metadata cleanup needed for publishing.
- `LICENSE`
  - Repository license text included in source distributions and wheel metadata.
- `.gitignore`
  - Ignore local build artifacts such as `dist/` and `build/`.
- `.github/workflows/ci.yml`
  - Branch and pull request validation workflow for `feature/*`, `develop`,
    `release/*`, `main`, and PRs, including `actionlint` validation for the
    workflow files themselves.
- `.github/workflows/release.yml`
  - Tag-driven publish workflow with permissions, concurrency, validation,
    build, PyPI upload, GitHub Release create-or-update, and back-merge PR
    creation.
- `README.md`
  - Primary user install path updated to `pipx install sql-query-mcp` and
    `pipx run --spec sql-query-mcp sql-query-mcp`, with linked release
    guidance.
- `docs/release-process.md`
  - Human-facing release runbook for PyPI secrets, release branch prep, tagging,
    failure recovery, and post-publish checks.
- `docs/git-workflow.md`
  - Formalize `release/vX.Y.Z` as the repository rule and align examples with
    the automated flow.

## Task 1: Verify release prerequisites and capture the current baseline

This task reduces avoidable surprises before any code or workflow changes. It
confirms the package name is publishable, records the current test baseline,
and ensures later failures are caused by new work rather than pre-existing
breakage.

**Files:**
- Read: `pyproject.toml`
- Read: `README.md`
- Read: `docs/git-workflow.md`
- Read: `docs/superpowers/specs/2026-03-20-release-and-pypi-automation-design.md`
- Test: `tests/`

- [ ] **Step 1: Run the current unit test suite before changes**

Run: `PYTHONPATH=. python3 -m unittest discover -s tests`
Expected: all current tests pass with no new failures.

- [ ] **Step 2: Check the intended PyPI distribution name**

Run: `python3 - <<'PY'
import json
import urllib.error
import urllib.request

url = 'https://pypi.org/pypi/sql-query-mcp/json'
try:
    with urllib.request.urlopen(url) as response:
        payload = json.load(response)
    print('exists', sorted(payload['releases'].keys())[-1] if payload['releases'] else 'no-releases')
except urllib.error.HTTPError as exc:
    if exc.code == 404:
        print('missing')
    else:
        raise
PY`
Expected: either `exists ...` or `missing`.

Interpret the result using this rule:

```text
- exists: manually confirm the PyPI project is already owned by this repository before continuing
- missing: treat the name as apparently available, but verify it again in PyPI before the first real publish
```

If the name is already owned by an unrelated project, stop implementation and
create a follow-up rename plan before changing workflows, docs, or package
metadata.

- [ ] **Step 3: Record the release invariants in scratch notes**

Keep this checklist beside the implementation work:

```text
- distribution name: sql-query-mcp
- import path: sql_query_mcp
- release branch: release/vX.Y.Z
- release tag: vX.Y.Z
- project.version: X.Y.Z
- public license text: confirm before Task 3
- maintainer display name: confirm before Task 3
```

- [ ] **Step 4: Install local verification tools**

Run: `python3 -m pip install --upgrade build twine`
Expected: `build` and `twine` install successfully into the active
environment.

Install `actionlint` using any supported local method for your environment.
Then run: `actionlint -version`
Expected: `actionlint` becomes available locally for pre-push workflow checks.

- [ ] **Step 5: Stop early if license or maintainer facts are still unclear**

If the repository still does not provide unambiguous license text or maintainer
display name after the prerequisite audit, stop and get those values from the
user before starting Task 3.

- [ ] **Step 6: Skip committing unless a tracked prerequisite note was added**

```bash
git add <only-if-you-created-a-tracked-note>
git commit -m "chore: record release prerequisites"
```

If no tracked files changed, do not create a commit.

## Task 2: Add a testable release metadata helper module

This task creates the only new Python logic needed for the release pipeline.
Keeping tag and branch parsing in a focused module makes the rules easy to test
and avoids burying fragile string parsing inside workflow YAML.

**Files:**
- Create: `sql_query_mcp/release_metadata.py`
- Create: `tests/test_release_metadata.py`
- Read: `pyproject.toml`

- [ ] **Step 1: Write the failing tests for version and branch parsing**

Create `tests/test_release_metadata.py` with coverage shaped like this:

```python
import tempfile
import unittest
from pathlib import Path

from sql_query_mcp.release_metadata import (
    build_release_context,
    decide_backmerge_action,
    parse_version_tag,
    resolve_effective_tag,
    should_skip_pypi_upload,
)


class ReleaseMetadataTestCase(unittest.TestCase):
    def test_parse_version_tag_accepts_v_prefix(self) -> None:
        self.assertEqual("0.2.0", parse_version_tag("v0.2.0"))

    def test_parse_version_tag_rejects_missing_v_prefix(self) -> None:
        with self.assertRaises(ValueError):
            parse_version_tag("0.2.0")

    def test_parse_version_tag_rejects_non_semver_tags(self) -> None:
        with self.assertRaises(ValueError):
            parse_version_tag("vnext")

    def test_build_release_context_derives_release_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pyproject = Path(temp_dir) / "pyproject.toml"
            pyproject.write_text("[project]\nversion = '0.2.0'\n", encoding="utf-8")
            context = build_release_context("v0.2.0", pyproject)

        self.assertEqual("0.2.0", context.version)
        self.assertEqual("release/v0.2.0", context.release_branch)

    def test_resolve_effective_tag_prefers_dispatch_input(self) -> None:
        self.assertEqual(
            "v0.2.0",
            resolve_effective_tag(
                event_name="workflow_dispatch",
                github_ref_name="develop",
                input_tag="v0.2.0",
            ),
        )

    def test_should_skip_pypi_upload_requires_recovery_confirmation(self) -> None:
        self.assertFalse(
            should_skip_pypi_upload(
                is_recovery_run=False,
                pypi_version_exists=True,
                recovery_confirmed=False,
            )
        )

    def test_decide_backmerge_action_for_main_never_skips(self) -> None:
        self.assertEqual("create", decide_backmerge_action("main", False, True))
```

- [ ] **Step 2: Run the targeted test file to verify it fails first**

If your local interpreter is Python 3.10, install the fallback parser before
running the tests:

Run: `python3 -m pip install tomli`
Expected: `tomli` installs successfully for local Python 3.10 test runs.

Run: `PYTHONPATH=. python3 -m unittest tests.test_release_metadata -v`
Expected: FAIL with `ModuleNotFoundError` or missing symbol errors for
`sql_query_mcp.release_metadata`.

- [ ] **Step 3: Implement the minimal helper module and CLI**

Create `sql_query_mcp/release_metadata.py` with focused pieces only:

```python
from __future__ import annotations

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from dataclasses import dataclass
from pathlib import Path
import argparse
import re


TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass(frozen=True)
class ReleaseContext:
    tag: str
    version: str
    release_branch: str


def resolve_effective_tag(event_name: str, github_ref_name: str, input_tag: str | None) -> str:
    if event_name == "workflow_dispatch":
        if not input_tag:
            raise ValueError("workflow_dispatch requires an explicit tag")
        return input_tag
    return github_ref_name


def parse_version_tag(tag: str) -> str:
    if not TAG_PATTERN.match(tag):
        raise ValueError("release tags must match vX.Y.Z")
    return tag[1:]


def read_project_version(pyproject_path: Path) -> str:
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    version = data.get("project", {}).get("version")
    if not version:
        raise ValueError("missing project.version")
    if not VERSION_PATTERN.match(version):
        raise ValueError("project.version must match X.Y.Z")
    return version


def build_release_context(tag: str, pyproject_path: Path) -> ReleaseContext:
    version = parse_version_tag(tag)
    project_version = read_project_version(pyproject_path)
    if version != project_version:
        raise ValueError("tag version does not match pyproject version")
    return ReleaseContext(tag=tag, version=version, release_branch=f"release/{tag}")


def should_skip_pypi_upload(
    is_recovery_run: bool,
    pypi_version_exists: bool,
    recovery_confirmed: bool,
) -> bool:
    return is_recovery_run and pypi_version_exists and recovery_confirmed


def decide_backmerge_action(target: str, has_open_pr: bool, has_diff: bool) -> str:
    if has_open_pr:
        return "reuse"
    if target == "main":
        return "create"
    if has_diff:
        return "create"
    return "skip"
```

Add a tiny CLI entry that prints workflow-friendly lines such as:

```text
version=0.2.0
release_branch=release/v0.2.0
tag=v0.2.0
```

- [ ] **Step 4: Re-run the targeted helper tests**

Run: `PYTHONPATH=. python3 -m unittest tests.test_release_metadata -v`
Expected: PASS.

- [ ] **Step 5: Run the helper CLI against the current repository version**

Run: `CURRENT_TAG="v$(python3 - <<'PY'
from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
data = tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8'))
version = data['project']['version']
print(version)
PY
)" && PYTHONPATH=. python3 -m sql_query_mcp.release_metadata --tag "$CURRENT_TAG" --pyproject pyproject.toml`
Expected: prints key/value lines including the current `version=` and matching
`release_branch=release/v<current-version>`.

- [ ] **Step 6: Commit the helper module and tests**

```bash
git add sql_query_mcp/release_metadata.py tests/test_release_metadata.py
git commit -m "test: add release metadata helpers"
```

## Task 3: Tighten package metadata for PyPI publication

This task makes the package credible as a real published distribution. The goal
is to improve metadata, include a license file, and ensure local build outputs
match what the release workflow will later upload.

**Files:**
- Modify: `pyproject.toml`
- Create: `LICENSE`
- Modify: `.gitignore`
- Test: `tests/test_release_metadata.py`

- [ ] **Step 1: Add a failing metadata test if helper coverage needs it**

If `tests/test_release_metadata.py` does not yet check project version reads,
add one more assertion like this:

```python
def test_read_project_version_reads_project_table(self) -> None:
    ...
    self.assertEqual("0.2.0", read_project_version(pyproject))
```

- [ ] **Step 2: Update `pyproject.toml` with PyPI-facing metadata**

Before editing, confirm the exact public license choice and author or
maintainer display name from existing repository facts or direct user guidance.
Do not invent values.

Keep the existing build backend and script entry point, then add only the
missing publish-facing fields:

```toml
[project]
# Preserve all existing runtime dependencies.
# Append this conditional dependency only if it is not already present.
# tomli>=2; python_version < '3.11'
license = { text = "<confirmed-license>" }
authors = [{ name = "<confirmed-author-or-maintainer>" }]
classifiers = [
  "License :: OSI Approved :: <confirmed-license-classifier>",
  "Programming Language :: Python :: 3",
  "Topic :: Database",
]

[tool.setuptools]
license-files = ["LICENSE"]
```

Do not switch away from `setuptools` in this task.

- [ ] **Step 3: Add the repository `LICENSE` file**

Create the exact confirmed license text file named `LICENSE`.

- [ ] **Step 4: Ignore local build artifacts**

Update `.gitignore` with at least:

```gitignore
build/
dist/
```

- [ ] **Step 5: Build the package locally**

Run: `rm -rf build dist ./*.egg-info && python3 -m build`
Expected: PASS and create both `dist/*.tar.gz` and `dist/*.whl`.

- [ ] **Step 6: Validate the generated metadata**

Run: `python3 -m twine check dist/*`
Expected: PASS with valid metadata and long description checks.

- [ ] **Step 7: Inspect built artifacts for the license file**

Run:

```bash
python3 - <<'PY'
import glob
import tarfile
import zipfile

sdist = glob.glob('dist/*.tar.gz')[0]
wheel = glob.glob('dist/*.whl')[0]

with tarfile.open(sdist, 'r:gz') as archive:
    sdist_names = archive.getnames()
with zipfile.ZipFile(wheel) as archive:
    wheel_names = archive.namelist()

assert any(name.endswith('/LICENSE') or name.endswith('LICENSE') for name in sdist_names)
assert any(name.endswith('/LICENSE') or name.endswith('LICENSE') for name in wheel_names)
PY
```

Expected: PASS and confirm `LICENSE` is present in both sdist and wheel.

- [ ] **Step 8: Commit the packaging metadata changes**

```bash
git add pyproject.toml LICENSE .gitignore
git commit -m "build: prepare package metadata for PyPI"
```

## Task 4: Add the branch and pull request CI workflow

This task adds the always-on validation workflow that catches problems before a
tagged release. Keep the workflow small: set up Python, install tooling, run
tests, and prove the package builds.

**Files:**
- Create: `.github/workflows/ci.yml`
- Read: `pyproject.toml`
- Read: `README.md`
- Test: `tests/`

- [ ] **Step 1: Create `.github/workflows/ci.yml` with the correct triggers**

Start with a workflow skeleton like this:

```yaml
name: CI

on:
  push:
    branches:
      - main
      - develop
      - 'feature/**'
      - 'release/**'
  pull_request:

jobs:
  lint-workflows:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: rhysd/actionlint@v1

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
```

- [ ] **Step 2: Add the exact validation commands used by this repository**

Keep the workflow split into two focused jobs:

```text
- lint-workflows: validate `.github/workflows/*.yml` with `actionlint`
- test: run Python tests and package build checks
```

Make the Python validation job run these commands in order:

```bash
python -m pip install --upgrade pip build
pip install -e .
PYTHONPATH=. python3 -m unittest discover -s tests
python -m build
```

- [ ] **Step 3: Run the same commands locally before trusting the workflow**

Run: `python3 -m pip install --upgrade pip build && pip install -e . && PYTHONPATH=. python3 -m unittest discover -s tests && python3 -m build`
Expected: PASS locally with a fresh `dist/` directory.

Run: `actionlint`
Expected: PASS with no workflow syntax or expression errors.

- [ ] **Step 4: Re-read the YAML to keep the job focused**

Do not add matrix builds, release publishing, or PR creation to `ci.yml`.
Keep `actionlint` in CI so workflow changes fail fast before release day.

- [ ] **Step 5: Commit the CI workflow**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add branch validation workflow"
```

## Task 5: Add the tagged release workflow with publish and back-merge PRs

This task is the center of the feature. It must stay strict about version
validation, publish sequencing, and idempotent recovery after partial success.

**Files:**
- Create: `.github/workflows/release.yml`
- Read: `sql_query_mcp/release_metadata.py`
- Read: `pyproject.toml`
- Test: `tests/test_release_metadata.py`

- [ ] **Step 1: Keep workflow-facing helper tests mandatory**

Add or retain tests for every workflow-facing branch the release logic depends
on, including CLI output, dispatch-tag validation, recovery skip gating,
tag/version mismatch failure, and back-merge decisions for both `main` and
`develop`. Use a test shaped like this:

```python
def test_cli_prints_release_context(self) -> None:
    ...
    self.assertIn("release_branch=release/v0.2.0", stdout)
```

- [ ] **Step 2: Create the `release.yml` trigger, permissions, and concurrency**

Start with this structure:

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:
    inputs:
      tag:
        description: Recovery tag such as v0.2.0
        required: true
      pypi_already_published:
        description: Confirm this is a post-publish recovery run
        required: true
        type: boolean

permissions:
  contents: write
  pull-requests: write

concurrency:
  group: release-${{ inputs.tag || github.ref_name }}
  cancel-in-progress: false

jobs:
  publish:
    runs-on: ubuntu-latest
    env:
      PYPI_API_TOKEN: ${{ secrets.PYPI_API_TOKEN }}
      GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          ref: ${{ github.event_name == 'workflow_dispatch' && inputs.tag || github.ref }}
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
```

- [ ] **Step 3: Add the validation and build steps before upload**

The workflow must do all of the following before publishing:

```bash
test -n "$GITHUB_TOKEN"
test -n "$GH_TOKEN"
python -m pip install --upgrade pip build twine
rm -rf build dist ./*.egg-info
pip install -e .
PYTHONPATH=. python3 -m unittest discover -s tests
python -m build
python -m twine check dist/*
python -m venv .release-smoke
. .release-smoke/bin/activate
pip install dist/*.whl
sql-query-mcp --help
deactivate
rm -rf .release-smoke
```

If GitHub auth tokens are missing, fail immediately with a clear error message
before building or editing releases or PRs. Check `PYPI_API_TOKEN` only in the
branch that will actually upload to PyPI.

Also use the helper CLI to derive `version` and `release_branch`, then fetch
the matching release branch and verify the tagged commit is reachable from it.

Use a bounded retry loop for the branch fetch so tag/branch push timing does
not create false negatives:

```bash
for attempt in 1 2 3 4 5; do
  git fetch origin "refs/heads/$RELEASE_BRANCH:refs/remotes/origin/$RELEASE_BRANCH" && break
  sleep 3
done
git merge-base --is-ancestor "$TAG" "origin/$RELEASE_BRANCH"
```

If the branch still cannot be fetched after the last retry, fail the workflow
with a clear message and stop before publishing. Treat a zero exit code from
`git merge-base --is-ancestor` as PASS; any non-zero exit code is a hard fail.

- [ ] **Step 4: Add the PyPI publish step with guarded rerun behavior**

Implement the publish logic so it behaves like this:

```bash
test -n "$PYPI_API_TOKEN"
python -m twine upload --non-interactive -u __token__ -p "$PYPI_API_TOKEN" dist/*
```

If a rerun happens after a confirmed successful publish of the same tag,
recognize that state and skip the duplicate upload instead of failing the whole
workflow.

Use this stricter rerun rule:

```text
- first run: always attempt the upload normally
- compensation rerun: only skip upload if the same tag is already confirmed as published for this repository
- uncertain state: fail and require manual confirmation instead of guessing
```

Use this decision procedure as the v1 source of truth:

```text
- tag push path: publish normally and write a clear success marker into the workflow summary
- compensation path: support `workflow_dispatch` recovery that requires the maintainer to provide the tag and confirm `pypi_already_published=true`
- if that confirmation is missing, do not skip upload just because a version exists remotely
```

Back the decision with an explicit existence check against PyPI before skipping
upload in a recovery run:

```bash
VERSION_TO_CHECK="$VERSION" python - <<'PY'
import json
import os
import urllib.error
import urllib.request

package = "sql-query-mcp"
version = os.environ["VERSION_TO_CHECK"]
url = f"https://pypi.org/pypi/{package}/json"
try:
    with urllib.request.urlopen(url) as response:
        payload = json.load(response)
except urllib.error.HTTPError as exc:
    if exc.code == 404:
        raise SystemExit(1)
    raise
raise SystemExit(0 if version in payload["releases"] else 1)
PY
```

Only skip upload when all three conditions are true: recovery run, explicit
maintainer confirmation, and the version exists in the PyPI JSON response.

- [ ] **Step 5: Add GitHub Release create-or-update behavior**

Use `gh` commands in the workflow so both first runs and compensation reruns are
safe:

First generate `release-notes.md` inside the workflow, then create or update the
GitHub Release from that file.

```bash
gh release view "$TAG" >/dev/null 2>&1 || gh release create "$TAG" dist/* --generate-notes
gh release view "$TAG" --json body --jq '.body' > auto-notes.md
cp auto-notes.md release-notes.md
printf '\n\n## Install\n\n`pipx install '\''sql-query-mcp==%s'\''`\n' "$VERSION" >> release-notes.md
gh release upload "$TAG" dist/* --clobber
gh release edit "$TAG" --title "$TAG" --notes-file release-notes.md
```

Pass GitHub authentication explicitly in the workflow job:

```bash
export GH_TOKEN="$GITHUB_TOKEN"
```

The final notes file must include at least one install command shaped like:

```text
pipx install 'sql-query-mcp==X.Y.Z'
```

- [ ] **Step 6: Add idempotent PR creation for `main` and `develop`**

Implement PR logic in the workflow with these branches:

```text
source: release/vX.Y.Z
targets: main, develop
```

Behavior rules:

```text
- main: always create or reuse `release/vX.Y.Z -> main`
- develop: create or reuse `release/vX.Y.Z -> develop`
- develop may skip PR creation only when an explicit compare shows no release-only changes remain
- fail loudly when API errors or unresolved branch state require manual action
```

Use this exact decision order for each target:

```text
1. Check whether an open PR already exists for the same source and target.
2. If one exists, reuse it and record the URL.
3. If target is main and no PR exists, create one.
4. If target is develop, run an explicit compare against the release branch.
5. If develop has no remaining release-only diff, record "no PR needed".
6. Otherwise create the develop PR.
7. On API failure, ambiguous branch state, or compare failure, stop and require manual recovery.
```

Use a concrete compare command for `develop`, for example:

```bash
git fetch origin develop
git rev-list --count "origin/develop..origin/$RELEASE_BRANCH"
```

Treat a result of `0` as "no remaining release-only commits" and allow the
skip. Any positive count means create the PR. Any fetch or compare error is a
hard failure, not a skip.

- [ ] **Step 7: Re-run the helper tests and local verification commands**

Run: `rm -rf build dist ./*.egg-info && PYTHONPATH=. python3 -m unittest tests.test_release_metadata -v && PYTHONPATH=. python3 -m unittest discover -s tests && python3 -m build && python3 -m twine check dist/*`
Expected: PASS, including helper coverage for effective tag resolution,
recovery-upload skip rules, and PR reuse or skip decisions.

- [ ] **Step 8: Commit the release workflow**

```bash
git add .github/workflows/release.yml sql_query_mcp/release_metadata.py tests/test_release_metadata.py
git commit -m "ci: automate tagged releases to PyPI"
```

## Task 6: Update user-facing docs for PyPI install and release operations

This task aligns the repository surface with the new workflow. Users need a
PyPI-first install path, and maintainers need a release runbook that matches
the automated branch and tag rules exactly.

**Files:**
- Modify: `README.md`
- Create: `docs/release-process.md`
- Modify: `docs/git-workflow.md`
- Read: `.github/workflows/release.yml`
- Read: `pyproject.toml`

- [ ] **Step 1: Rewrite the README quick start around PyPI installation**

Replace the top install path with content shaped like this:

```md
## Quick start

1. Choose installed command mode with `pipx install sql-query-mcp`, or managed
   launch mode with `pipx run --spec sql-query-mcp sql-query-mcp`.
2. Save your config file outside the repository.
3. Put `SQL_QUERY_MCP_CONFIG` and real DSNs in the MCP client's environment
   block.
4. Register the server in your MCP client.
```

Keep editable install instructions in the development section, not the main
user path.

Also add one short clarification near install or development setup:

```text
PyPI install name: sql-query-mcp
Python import path: sql_query_mcp
```

Add one short note that points users to versioned installs and GitHub Releases,
for example:

```text
Install a specific release with `pipx install 'sql-query-mcp==X.Y.Z'`.
Published release artifacts are also attached to each GitHub Release.
```

- [ ] **Step 2: Add `docs/release-process.md` as the release runbook**

Cover these sections in order:

```md
## Prerequisites
## Prepare `release/vX.Y.Z`
## Push branch, then push tag
## Watch the release workflow
## Verify PyPI and GitHub Release
## Merge the back-merge PRs
## Recovery when publish succeeds but follow-up steps fail
```

Include the required secret name exactly: `PYPI_API_TOKEN`.

- [ ] **Step 3: Update `docs/git-workflow.md` to formalize `release/vX.Y.Z`**

Make the abstract rule and examples match each other. The release section must
say the branch format is `release/vX.Y.Z`, not a vague `release/<version>`.

- [ ] **Step 4: Re-read links and command examples across the edited docs**

Check that these references all exist and agree with the workflow behavior:

```text
README.md
docs/release-process.md
docs/git-workflow.md
.github/workflows/release.yml
```

- [ ] **Step 5: Run the full verification stack after the doc updates**

Run: `rm -rf build dist ./*.egg-info && PYTHONPATH=. python3 -m unittest discover -s tests && python3 -m build && python3 -m twine check dist/*`
Expected: PASS.

- [ ] **Step 6: Commit the documentation updates**

```bash
git add README.md docs/release-process.md docs/git-workflow.md
git commit -m "docs: document PyPI install and release flow"
```

## Task 7: Perform final release-readiness verification

This final task checks the whole feature as a maintainer would. It is the last
chance to catch mismatches between code, workflow assumptions, and human docs
before opening a PR.

**Files:**
- Read: `.github/workflows/ci.yml`
- Read: `.github/workflows/release.yml`
- Read: `README.md`
- Read: `docs/release-process.md`
- Read: `docs/git-workflow.md`
- Test: `tests/`

- [ ] **Step 1: Run the full local validation sequence from a clean shell**

Run: `python3 -m pip install --upgrade pip build twine && rm -rf build dist ./*.egg-info && pip install -e . && PYTHONPATH=. python3 -m unittest discover -s tests && python3 -m build && python3 -m twine check dist/*`
Expected: PASS.

- [ ] **Step 2: Run the installed CLI smoke test from the built wheel**

Run: `python3 -m venv .release-final && . .release-final/bin/activate && pip install dist/*.whl && sql-query-mcp --help && deactivate && rm -rf .release-final`
Expected: PASS and print command help instead of hanging or failing import.

- [ ] **Step 3: Dry-run the helper CLI for the current repository version**

Run: `CURRENT_TAG="v$(python3 - <<'PY'
from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
data = tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8'))
version = data['project']['version']
print(version)
PY
)" && PYTHONPATH=. python3 -m sql_query_mcp.release_metadata --tag "$CURRENT_TAG" --pyproject pyproject.toml`
Expected: PASS and print the current release branch mapping.

- [ ] **Step 4: Verify workflow validation after push**

After pushing the branch that contains the workflow files, confirm in GitHub
Actions that the `CI` workflow starts and that the `lint-workflows` job passes.
Run `actionlint` locally before pushing:

```bash
actionlint
```

Expected: local `actionlint` passes if installed, and GitHub shows a successful
`lint-workflows` job for the pushed branch.

- [ ] **Step 5: Review the final diff for v1-only scope discipline**

Confirm the diff contains only:

```text
- metadata and license changes
- helper module and tests
- ci.yml and release.yml
- README/release-process/git-workflow doc updates
```

Do not add TestPyPI, changelog automation, multi-version matrix builds, or
hotfix release automation in this PR.

- [ ] **Step 6: Create the final implementation commit or PR-ready commit stack**

```bash
git add pyproject.toml LICENSE .gitignore .github/workflows/ci.yml .github/workflows/release.yml sql_query_mcp/release_metadata.py tests/test_release_metadata.py README.md docs/release-process.md docs/git-workflow.md
git commit -m "feat: add automated PyPI release workflow"
```

If you already committed task-by-task, keep the logical commit stack and skip a
duplicate squash-style commit.
