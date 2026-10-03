# Claude Code routes — task-worktree

`SKILL.md` names the operations. This file names how a Claude Code session
performs them. Oh My Pi's route is in [`omp.md`](omp.md), and Codex's in
[`codex.md`](codex.md).

Require Worktrunk (`wt`) before setup. If it is absent, report that it must be
installed and stop. Do not use bare Git worktree creation as a fallback.

Use `Bash` for Git boundary reads and Worktrunk:

```sh
git rev-parse --show-toplevel
git branch --show-current
git remote
git config --get remote.pushDefault
git symbolic-ref --short refs/remotes/<remote>/HEAD
git -C <primary-worktree> status --short
wt --config-set 'list.json-schema=2' list --format=json
wt config show
wt switch --create <task-branch> --base <resolved-base> --no-cd --format=json
wt switch <task-branch> --no-cd --format=json
```

Use the remote declared by the task or repository, then `remote.pushDefault`,
then the only configured remote. More than one unexplained remote is a stop.
Keep the full remote-tracking name returned by `git symbolic-ref` as the base.
Never use the current feature branch as the base.

Inspect `.items[]` from schema-2 JSON. `.worktree.main` identifies the primary
worktree; `.worktree.path` supplies its path. `wt config show` reports config
locations and the project identifier, not the effective path value. Inspect
`WORKTRUNK_WORKTREE_PATH`, system/user `worktree-path` settings, and the
matching project-specific settings in system/user config. If none is set,
Worktrunk's documented default is
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

Claude Code's native `WorktreeCreate` hook is separate from this route. The
official Worktrunk hook calls `wt switch --create` without this procedure's
explicit `--base`, so it does not enforce the resolved task base. Use the
explicit-base command above; do not fork or override the upstream hook.

In a detached worktree already dedicated to the task, attach in place with
`git switch <task-branch>` or `git switch -c <task-branch> <resolved-base>`.
This is Worktrunk's documented method to change the branch of an existing
worktree, not a fallback for creating one. Stop and inspect branch or path
collisions; do not force them.

`Bash` does not relocate the session for later calls. Prefix each later shell
command with `cd <task-worktree> &&`, or use a command's own directory option.
Pass absolute task-worktree paths to `Read`, `Write`, `Edit`, `Glob`, and
`Grep`. Give the same absolute path to an `Agent` handling a delegated slice.
Verify registration and branch with Worktrunk JSON and Git, then compare the
primary status with its setup baseline before delivery. Use `wt remove` for
later manual cleanup, never bare `git worktree remove`.
