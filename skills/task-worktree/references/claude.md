# Claude Code routes — task-worktree

`SKILL.md` names the operations. This file names how a Claude Code session
performs them. Oh My Pi's route is in [`omp.md`](omp.md), and Codex's in
[`codex.md`](codex.md).

Use `Bash` for the Git setup:

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

`Bash` does not relocate the session for later calls. Prefix each later shell
command with `cd <task-worktree> &&`, or use a command's own directory option.
Pass absolute task-worktree paths to `Read`, `Write`, `Edit`, `Glob`, and
`Grep`. Give the same absolute path to an `Agent` handling a delegated slice.
Verify with `git -C <task-worktree> branch --show-current` and compare
`git -C <primary-worktree> status --short` with the setup baseline before
delivery.
