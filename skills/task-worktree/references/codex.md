# Codex routes — task-worktree

`SKILL.md` names the operations. This file names how a Codex session performs
them. Claude Code's route is in [`claude.md`](claude.md), and Oh My Pi's in
[`omp.md`](omp.md).

Use the shell for the Git commands in `SKILL.md`. Git or the user's chosen
tool may create the dedicated registered non-primary worktree. Worktrunk is
optional; neither installation nor sibling placement is required.

```sh
git rev-parse --show-toplevel
git branch --show-current
git remote
git config --get remote.pushDefault
git symbolic-ref --short refs/remotes/<remote>/HEAD
git worktree list --porcelain -z
git fetch <remote> +refs/heads/<base-branch>:refs/remotes/<remote>/<base-branch>
git -C <primary-worktree> status --short
git worktree add -b <task-branch> <task-path> <resolved-base>
```

Use the task record's branch before a new designation; otherwise use exactly
one designated branch, then the project convention or a short issue-based
name. Codex keeps one local/remote identity. The primary-held designation
exception is Claude-specific.

For a recorded remote branch, fetch its exact ref first. A remote-only branch
uses `git worktree add --track -b <task-branch> <task-path>
<remote>/<task-branch>`. An existing free local branch uses
`git worktree add <task-path> <task-branch>`. A registered same-task worktree
is reused directly. Advance a resumed branch with `git merge --ff-only
<remote>/<task-branch>` inside it; inspect a failed fast-forward as a collision.
Do not recreate it from the base.

Parse Git's NUL-delimited registration records. Verify the non-primary task
path and ownership, canonical non-overlap, and branch/path collisions.
Preserve the chosen tool's hooks and approval rules. External worktrees and
paths with spaces are valid.

A detached non-primary task worktree may be edited. Before committing, create
a recovery branch at its current HEAD with `git switch -c <task-branch>`.
For an existing recorded branch, confirm its tip equals that HEAD and is free
before attaching. Never switch away from unrelated changes or abandon commits.

Set `workdir` to the task worktree on every shell call. Run patch operations
there and use absolute paths for direct file operations. Give delegated
slices the same root. Coordinate shared-ref and same-worktree writers; never
make ordinary commits to `master`. Compare the primary status with its setup
baseline before delivery and report external changes without undoing them.
