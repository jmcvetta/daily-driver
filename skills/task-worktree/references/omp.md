# Oh My Pi routes — task-worktree

`SKILL.md` names the operations. This file names how an Oh My Pi session
performs them. Claude Code's route is in [`claude.md`](claude.md), and Codex's
in [`codex.md`](codex.md).

Use the `bash` tool for the Git setup:

```sh
git rev-parse --show-toplevel
git branch --show-current
git worktree list --porcelain
git symbolic-ref --short refs/remotes/origin/HEAD
git status --short
git worktree add -b <task-branch> <sibling-path> <base>
```

The first entry from `git worktree list --porcelain` is the primary worktree.
Strip the remote prefix from `refs/remotes/origin/HEAD` when it supplies the
base. If the task branch already exists, omit `-b` and put the branch last. In
a detached worktree already dedicated to the task, use `git switch -c
<task-branch> <base>` there instead of adding another worktree.

Set `cwd` to the task worktree on every later `bash` call. Pass absolute
task-worktree paths to `read`, `write`, `edit`, `glob`, and `grep`. Give the
same absolute path to a `task` handling a delegated slice. Verify with
`git -C <task-worktree> branch --show-current` and compare
`git -C <primary-worktree> status --short` with the setup baseline before
delivery.
