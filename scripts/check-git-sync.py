#!/usr/bin/env python3
"""Exercise Worktrunk sync against disposable Git repositories, never this checkout.

Sync removes every branch and worktree Worktrunk reports as integrated into
master, including squash-merged ones, and leaves unmerged, dirty, or locked
work alone.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def run(
    cwd: Path, *args: str, env: dict[str, str] | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=check)


def branch_exists(repo: Path, branch: str = "stale") -> bool:
    return (
        run(repo, "git", "show-ref", "--verify", f"refs/heads/{branch}", check=False).returncode
        == 0
    )


def remote_ref_exists(repo: Path, branch: str) -> bool:
    return (
        run(
            repo,
            "git",
            "show-ref",
            "--verify",
            f"refs/remotes/origin/{branch}",
            check=False,
        ).returncode
        == 0
    )


class SyncTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="wt-sync-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.primary = self.root / "master worktree"
        self.remote = self.root / "remote.git"
        self.linked = self.root / "stale worktree"
        self.env = os.environ.copy()
        config = self.root / "user.toml"
        config.write_text("skip-shell-integration-prompt = true\n", encoding="utf-8")
        system = self.root / "system.toml"
        system.touch()
        self.env.update(WORKTRUNK_CONFIG_PATH=str(config), WORKTRUNK_SYSTEM_CONFIG_PATH=str(system))
        self.env.pop("WORKTRUNK_PROJECT_CONFIG_PATH", None)
        self.env.pop("WORKTRUNK_WORKTREE_PATH", None)

        run(self.root, "git", "init", "--bare", "--initial-branch=master", str(self.remote))
        run(self.root, "git", "init", "--initial-branch=master", str(self.primary))
        (self.primary / ".config").mkdir()
        shutil.copy2(ROOT / ".config/wt.toml", self.primary / ".config/wt.toml")
        shutil.copy2(ROOT / "Makefile", self.primary / "Makefile")
        (self.primary / "tracked.txt").write_text("master\n", encoding="utf-8")
        run(self.primary, "git", "config", "user.name", "Sync Test")
        run(self.primary, "git", "config", "user.email", "sync@example.invalid")
        run(self.primary, "git", "add", "Makefile", ".config/wt.toml", "tracked.txt")
        run(self.primary, "git", "commit", "-m", "seed")
        run(self.primary, "git", "remote", "add", "origin", str(self.remote))
        run(self.primary, "git", "push", "-u", "origin", "master")
        run(self.primary, "git", "worktree", "add", "-b", "stale", str(self.linked), "master")
        (self.linked / "tracked.txt").write_text("integrated\n", encoding="utf-8")
        run(self.linked, "git", "add", "tracked.txt")
        run(self.linked, "git", "commit", "-m", "integrated change")
        run(self.linked, "git", "push", "-u", "origin", "stale")
        run(self.primary, "git", "push", "origin", "--delete", "stale")

    def sync(self, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        command = 'set -e; eval "$(command wt config shell init bash)"; wt -y sync; pwd'
        return run(cwd or self.primary, "bash", "--noprofile", "--norc", "-c", command, env=self.env)

    def publish_upstream(self, branch: str = "stale") -> None:
        run(self.primary, "git", "push", "-u", "origin", branch)

    def integrate_fast_forward(self) -> None:
        run(self.primary, "git", "merge", "--ff-only", "stale")
        run(self.primary, "git", "push", "origin", "master")

    def integrate_squash(self) -> None:
        run(self.primary, "git", "merge", "--squash", "stale")
        run(self.primary, "git", "commit", "-m", "integrate stale by squash")
        run(self.primary, "git", "push", "origin", "master")

    def add_caller(self) -> Path:
        caller = self.root / "caller worktree"
        run(self.primary, "git", "worktree", "add", "-b", "caller", str(caller), "master")
        return caller

    def test_linked_caller_returns_to_master_and_removes_merged_worktrees(self) -> None:
        """Shell integration leaves the caller in master before integrated worktrees are removed."""
        caller = self.add_caller()
        self.integrate_fast_forward()
        result = self.sync(caller)
        self.assertEqual(result.stdout.splitlines()[-1], str(self.primary))
        self.assertFalse(self.linked.exists())
        self.assertFalse(branch_exists(self.primary))
        self.assertFalse(caller.exists())
        self.assertFalse(branch_exists(self.primary, "caller"))

    def test_fast_forward_merged_branch_removes_worktree_and_branch(self) -> None:
        """A branch whose commits master contains is removed with its worktree."""
        self.integrate_fast_forward()
        self.sync()
        self.assertFalse(self.linked.exists())
        self.assertFalse(branch_exists(self.primary))

    def test_squash_integrated_branch_with_live_upstream_is_removed(self) -> None:
        """A squash merge leaves no shared commit; an ancestry-only selector keeps it."""
        self.publish_upstream()
        self.integrate_squash()
        result = self.sync()
        self.assertFalse(self.linked.exists())
        self.assertFalse(branch_exists(self.primary))
        self.assertTrue(remote_ref_exists(self.primary, "stale"))
        self.assertNotIn("could not be removed", result.stderr)

    def test_merged_direct_branch_with_live_upstream_is_removed(self) -> None:
        """An existing remote must not keep a merged local branch alive."""
        tip = run(self.primary, "git", "rev-parse", "master").stdout.strip()
        run(self.primary, "git", "branch", "direct", tip)
        self.publish_upstream("direct")
        self.sync()
        self.assertFalse(branch_exists(self.primary, "direct"))
        self.assertTrue(remote_ref_exists(self.primary, "direct"))

    def test_merged_linked_branch_with_live_upstream_is_removed(self) -> None:
        """Merged cleanup must include linked worktrees whose upstreams still exist."""
        self.publish_upstream()
        self.integrate_fast_forward()
        self.sync()
        self.assertFalse(self.linked.exists())
        self.assertFalse(branch_exists(self.primary))
        self.assertTrue(remote_ref_exists(self.primary, "stale"))

    def test_merged_branch_without_upstream_metadata_is_removed(self) -> None:
        """A fully integrated branch needs no tracking metadata to be removed."""
        self.integrate_fast_forward()
        run(self.primary, "git", "branch", "--unset-upstream", "stale")
        self.sync()
        self.assertFalse(self.linked.exists())
        self.assertFalse(branch_exists(self.primary))

    def test_unmerged_branch_with_live_upstream_is_kept(self) -> None:
        """Cleanup must not remove a worktree that still adds commits."""
        (self.linked / "new.txt").write_text("unpublished\n", encoding="utf-8")
        run(self.linked, "git", "add", "new.txt")
        run(self.linked, "git", "commit", "-m", "unpublished change")
        self.publish_upstream()
        self.sync()
        self.assertTrue(self.linked.exists())
        self.assertTrue(branch_exists(self.primary))

    def test_unmerged_branch_without_upstream_is_kept(self) -> None:
        """An unintegrated branch needs no tracking metadata to be worth keeping."""
        run(self.primary, "git", "branch", "--unset-upstream", "stale")
        self.sync()
        self.assertTrue(self.linked.exists())
        self.assertTrue(branch_exists(self.primary))

    def test_gone_upstream_does_not_delete_unmerged_branch(self) -> None:
        """A gone remote ref alone must not destroy an unpublished linked worktree."""
        self.sync()
        self.assertTrue(self.linked.exists())
        self.assertTrue(branch_exists(self.primary))

    def test_dirty_stale_worktree_is_kept(self) -> None:
        """Cleanup must not delete user files or the branch that owns them."""
        (self.linked / "user-data.txt").write_text("keep\n", encoding="utf-8")
        self.integrate_fast_forward()
        result = self.sync()
        self.assertEqual(result.stdout.splitlines()[-1], str(self.primary))
        self.assertNotIn("could not be removed", result.stderr)
        self.assertTrue(self.linked.exists())
        self.assertEqual((self.linked / "user-data.txt").read_text(encoding="utf-8"), "keep\n")
        self.assertTrue(branch_exists(self.primary))

    def test_locked_stale_worktree_is_kept(self) -> None:
        """An integrated branch must not take a locked worktree."""
        self.integrate_fast_forward()
        run(self.primary, "git", "worktree", "lock", str(self.linked))
        self.sync()
        self.assertTrue(self.linked.exists())
        self.assertTrue(branch_exists(self.primary))

    def test_advanced_stale_worktree_is_kept(self) -> None:
        """A commit made after integration must keep the worktree alive."""
        self.integrate_fast_forward()
        (self.linked / "later.txt").write_text("later work\n", encoding="utf-8")
        run(self.linked, "git", "add", "later.txt")
        run(self.linked, "git", "commit", "-m", "later work")
        self.sync()
        self.assertTrue(self.linked.exists())
        self.assertTrue(branch_exists(self.primary))

    def test_dirty_worktree_does_not_block_direct_branch_cleanup(self) -> None:
        """A refused worktree removal must not stop cleanup of later safe branches."""
        self.integrate_fast_forward()
        tip = run(self.primary, "git", "rev-parse", "master").stdout.strip()
        run(self.primary, "git", "branch", "direct", tip)
        self.publish_upstream("direct")
        (self.linked / "untracked.txt").write_text("keep\n", encoding="utf-8")
        self.sync()
        self.assertTrue(self.linked.exists())
        self.assertTrue(branch_exists(self.primary))
        self.assertFalse(branch_exists(self.primary, "direct"))


if __name__ == "__main__":
    unittest.main()
