import subprocess
import tempfile
import unittest
from pathlib import Path

from run_action import resolve_baseline, resolve_root


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()


class BaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.repo = Path(tmp.name) / "upstream"
        cls.repo.mkdir()
        git(cls.repo, "init", "-b", "main")
        git(cls.repo, "config", "user.name", "Action Test")
        git(cls.repo, "config", "user.email", "test@example.invalid")
        git(cls.repo, "config", "commit.gpgsign", "false")
        git(cls.repo, "commit", "--allow-empty", "-m", "Common ancestor")
        cls.common = git(cls.repo, "rev-parse", "HEAD")

        git(cls.repo, "switch", "-c", "feature")
        (cls.repo / "feature.py").write_text("enabled = True\n", encoding="utf-8")
        git(cls.repo, "add", "feature.py")
        git(cls.repo, "commit", "-m", "Add feature")
        cls.feature = git(cls.repo, "rev-parse", "HEAD")

        git(cls.repo, "switch", "main")
        (cls.repo / "base.py").write_text("version = 2\n", encoding="utf-8")
        git(cls.repo, "add", "base.py")
        git(cls.repo, "commit", "-m", "Advance base branch")
        cls.base = git(cls.repo, "rev-parse", "HEAD")
        git(cls.repo, "branch", "review;v1", cls.base)

        git(cls.repo, "switch", "-c", "test-merge")
        git(cls.repo, "merge", "--no-ff", "feature", "-m", "Test merge")
        cls.merge = git(cls.repo, "rev-parse", "HEAD")

    def setUp(self):
        git(self.repo, "switch", "--detach", self.feature)

    def test_merge_checkout_compares_the_merged_tree_to_the_event_base(self):
        git(self.repo, "switch", "--detach", self.merge)
        self.assertEqual(
            resolve_baseline(self.repo, "pull_request", "", self.base, self.feature),
            self.base,
        )

    def test_head_checkout_compares_to_the_common_ancestor(self):
        self.assertEqual(
            resolve_baseline(self.repo, "pull_request", "", self.base, self.feature),
            self.common,
        )

    def test_checkout_of_the_base_branch_is_rejected(self):
        git(self.repo, "switch", "--detach", self.base)
        with self.assertRaises(ValueError):
            resolve_baseline(self.repo, "pull_request", "", self.base, self.feature)

    def test_merge_from_another_pr_head_is_rejected(self):
        git(self.repo, "switch", "--detach", self.merge)
        with self.assertRaises(ValueError):
            resolve_baseline(self.repo, "pull_request", "", self.base, self.common)

    def test_missing_base_history_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "shallow"
            git(
                self.repo, "clone", "--no-local", "--depth=1",
                "--branch", "feature", str(self.repo), str(clone),
            )
            with self.assertRaises(ValueError):
                resolve_baseline(clone, "pull_request", "", self.base, self.feature)

    def test_other_events_require_an_explicit_ref(self):
        with self.assertRaises(ValueError):
            resolve_baseline(self.repo, "workflow_dispatch", "", "", "")

    def test_an_explicit_ref_is_literal(self):
        self.assertEqual(
            resolve_baseline(self.repo, "workflow_dispatch", "review;v1", "", ""),
            self.base,
        )


class RootTests(unittest.TestCase):
    def test_space_in_relative_directory_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            git(workspace, "init", "-b", "main")
            target = workspace / "service package"
            target.mkdir()
            self.assertEqual(resolve_root(workspace, "service package"), target)

    def test_path_outside_the_workspace_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "checkout"
            workspace.mkdir()
            with self.assertRaises(ValueError):
                resolve_root(workspace, "..")


if __name__ == "__main__":
    unittest.main()
