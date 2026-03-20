from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sql_query_mcp.release_metadata import (
    build_release_context,
    decide_backmerge_action,
    parse_version_tag,
    read_project_version,
    resolve_effective_tag,
    should_skip_pypi_upload,
)


class ReleaseMetadataTestCase(unittest.TestCase):
    def test_parse_version_tag_accepts_semver_tag(self) -> None:
        self.assertEqual("0.2.0", parse_version_tag("v0.2.0"))

    def test_parse_version_tag_rejects_missing_v_prefix(self) -> None:
        with self.assertRaises(ValueError):
            parse_version_tag("0.2.0")

    def test_parse_version_tag_rejects_non_semver(self) -> None:
        with self.assertRaises(ValueError):
            parse_version_tag("vnext")

    def test_read_project_version_reads_project_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pyproject = Path(temp_dir) / "pyproject.toml"
            pyproject.write_text(
                '[project]\nname = "sql-query-mcp"\nversion = "0.2.0"\n',
                encoding="utf-8",
            )

            self.assertEqual("0.2.0", read_project_version(pyproject))

    def test_build_release_context_derives_release_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pyproject = Path(temp_dir) / "pyproject.toml"
            pyproject.write_text(
                '[project]\nname = "sql-query-mcp"\nversion = "0.2.0"\n',
                encoding="utf-8",
            )

            context = build_release_context("v0.2.0", pyproject)

        self.assertEqual("v0.2.0", context.tag)
        self.assertEqual("0.2.0", context.version)
        self.assertEqual("release/v0.2.0", context.release_branch)

    def test_build_release_context_rejects_version_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pyproject = Path(temp_dir) / "pyproject.toml"
            pyproject.write_text(
                '[project]\nname = "sql-query-mcp"\nversion = "0.3.0"\n',
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                build_release_context("v0.2.0", pyproject)

    def test_resolve_effective_tag_uses_dispatch_input(self) -> None:
        self.assertEqual(
            "v0.2.0",
            resolve_effective_tag(
                event_name="workflow_dispatch",
                github_ref_name="develop",
                input_tag="v0.2.0",
            ),
        )

    def test_resolve_effective_tag_requires_dispatch_input(self) -> None:
        with self.assertRaises(ValueError):
            resolve_effective_tag(
                event_name="workflow_dispatch",
                github_ref_name="develop",
                input_tag=None,
            )

    def test_should_skip_pypi_upload_requires_all_conditions(self) -> None:
        self.assertTrue(
            should_skip_pypi_upload(
                is_recovery_run=True,
                pypi_version_exists=True,
                recovery_confirmed=True,
            )
        )
        self.assertFalse(
            should_skip_pypi_upload(
                is_recovery_run=True,
                pypi_version_exists=False,
                recovery_confirmed=True,
            )
        )

    def test_decide_backmerge_action_for_main_never_skips(self) -> None:
        self.assertEqual("create", decide_backmerge_action("main", False, False))

    def test_decide_backmerge_action_reuses_existing_pr(self) -> None:
        self.assertEqual("reuse", decide_backmerge_action("develop", True, True))

    def test_decide_backmerge_action_skips_develop_without_diff(self) -> None:
        self.assertEqual("skip", decide_backmerge_action("develop", False, False))

    def test_cli_prints_release_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pyproject = Path(temp_dir) / "pyproject.toml"
            pyproject.write_text(
                '[project]\nname = "sql-query-mcp"\nversion = "0.2.0"\n',
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "sql_query_mcp.release_metadata",
                    "--tag",
                    "v0.2.0",
                    "--pyproject",
                    str(pyproject),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertIn("tag=v0.2.0", result.stdout)
        self.assertIn("version=0.2.0", result.stdout)
        self.assertIn("release_branch=release/v0.2.0", result.stdout)


if __name__ == "__main__":
    unittest.main()
