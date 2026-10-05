# Codex routes — task-worktree

`SKILL.md` names the operations. This file names how a Codex session performs
them. Claude Code's route is in [`claude.md`](claude.md), and Oh My Pi's in
[`omp.md`](omp.md).

Before Worktrunk worktree inspection, source `scripts/ensure-worktrunk.sh`
from the repository root and run `ensure_worktrunk`. It returns without
installing when `wt` exists. If missing, it uses Homebrew or Cargo in user
scope, adds the installed bin directory to this shell's `PATH`, and verifies
`wt --version`. It never upgrades `wt`; if neither installer works, stop with
the helper's cause and actionable installation requirement. Do not use bare
Git worktree creation as a fallback.

Use the shell for Git boundary reads and Worktrunk:

```sh
git rev-parse --show-toplevel
git branch --show-current
git remote
git config --get remote.pushDefault
git symbolic-ref --short refs/remotes/<remote>/HEAD
git -C <primary-worktree> status --short
source scripts/ensure-worktrunk.sh && ensure_worktrunk
wt --config-set 'list.json-schema=2' list --format=json
wt config show
wt switch --create <task-branch> --base <resolved-base> --no-cd --format=json
wt switch <task-branch> --no-cd --format=json
git fetch <remote> +refs/heads/<task-branch>:refs/remotes/<remote>/<task-branch>
wt switch --create <task-branch> --base <remote>/<task-branch> --no-cd --format=json
git -C <task-worktree> merge --ff-only <remote>/<task-branch>
git switch --track -c <task-branch> <remote>/<task-branch>
```

Use the remote declared by the task or repository, then `remote.pushDefault`,
then the only configured remote. More than one unexplained remote is a stop.
Keep the full remote-tracking name returned by `git symbolic-ref` as the base.
Never use the current feature branch as the base.

Inspect `.items[]` from schema-2 JSON. `.worktree.main` identifies the primary
worktree; `.worktree.path` supplies its path. `wt config show` reports config
locations and the project identifier, not the effective path value. Inspect
`WORKTRUNK_WORKTREE_PATH`, system/user `worktree-path` settings, and matching
project-specific settings in system/user config. If none is set, Worktrunk's
documented default is
`{{ repo_path }}/../{{ repo }}.{{ branch | sanitize }}`. Resolve that template
for this task before creating: its path must be beside the primary worktree
and outside every existing worktree. Do not change user configuration to make
the policy fit.

Use the task branch from the task record before a new per-session designation.
Otherwise use exactly one branch designated for this task, then the project
convention or a short issue-based name. Reuse only a worktree already dedicated
to this task. For a new branch use `wt switch --create`; for an existing free
branch use `wt switch`. Parse `.path` from successful stdout JSON only; stderr
is diagnostics. Do not use `--clobber`, `--yes`, or `--no-hooks`.

An existing task branch from the task record is not a new branch. Fetch the
selected remote ref with the explicit refspec above. If no local branch exists,
use `wt switch --create <task-branch> --base <remote>/<task-branch>` to attach
it to its remote tip; matching names retain tracking. If the local branch
exists, use `wt switch`, then run `git -C <returned-path> merge --ff-only
<remote>/<task-branch>`. A failed fast-forward or a branch held by another task
is a collision, not a reason to recreate it from the default base. In a
dedicated detached task worktree, use `git switch --track -c <task-branch>
<remote>/<task-branch>` for a remote-only task branch, then fast-forward it.
Fresh task branches still start from the resolved base.

In a detached worktree already dedicated to the task, attach in place with
`git switch <task-branch>` or `git switch -c <task-branch> <resolved-base>`.
This is Worktrunk's documented method to change the branch of an existing
worktree, not a fallback for creating one. Stop and inspect branch or path
collisions; do not force them.

Set `workdir` to the task worktree on every later shell call. Run patch
operations from that worktree and use absolute task-worktree paths for direct
file operations. Give the same absolute path to a delegated agent. Verify
registration and branch with Worktrunk JSON and Git, then compare the primary
status with its setup baseline before delivery. Use `wt remove` for later
manual cleanup, never bare `git worktree remove`.
