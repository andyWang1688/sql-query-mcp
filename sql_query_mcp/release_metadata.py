from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib  # type: ignore[import-not-found]


TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass(frozen=True)
class ReleaseContext:
    tag: str
    version: str
    release_branch: str


def resolve_effective_tag(
    event_name: str, github_ref_name: str, input_tag: str | None
) -> str:
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
    github_release_exists: bool,
) -> bool:
    if not pypi_version_exists:
        return False
    if is_recovery_run and recovery_confirmed:
        return True
    return github_release_exists


def decide_backmerge_action(target: str, has_open_pr: bool, has_diff: bool) -> str:
    if has_open_pr:
        return "reuse"
    if target == "main":
        return "create"
    if has_diff:
        return "create"
    return "skip"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve release metadata.")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--pyproject", required=True)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    context = build_release_context(args.tag, Path(args.pyproject))
    print(f"tag={context.tag}")
    print(f"version={context.version}")
    print(f"release_branch={context.release_branch}")


if __name__ == "__main__":
    main()
