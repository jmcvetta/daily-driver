# Oh My Pi routes — task-worktree

`SKILL.md` names the operations. This file names how an Oh My Pi session
performs them. Claude Code's route is in [`claude.md`](claude.md), and Codex's
in [`codex.md`](codex.md).

Before Worktrunk worktree inspection, locate the helper in the loaded Daily
Driver plugin, not in the target repository. Take the absolute path of the
loaded `skills/task-worktree/SKILL.md` from the skill read result. Its parent
is `task-worktree`; the next parent is `skills`; the next parent is the plugin
root. Resolve
`<plugin-root>/scripts/ensure-worktrunk.sh`, verify that the resolved file is
readable, then source that quoted absolute path and run `ensure_worktrunk`.
If the file is unavailable, report the resolved path and stop. Do not fall
back to a helper under the target repository. The helper returns without
installing when `wt` exists. If missing, it uses Homebrew or Cargo in user
scope, adds the installed bin directory to this shell's `PATH`, and verifies
`wt --version`. Resolve, source and run it again in each later shell
invocation that uses `wt`; it restores the installed bin path without
reinstalling. It never upgrades `wt`; if neither installer works, stop with
the helper's cause and actionable installation requirement. Do not use bare
Git worktree creation as a fallback.

Use the `bash` tool for Git boundary reads and Worktrunk:

```sh
git rev-parse --show-toplevel
git branch --show-current
git remote
git config --get remote.pushDefault
git symbolic-ref --short refs/remotes/<remote>/HEAD
git -C <primary-worktree> status --short
# Replace this with the absolute skills/task-worktree/SKILL.md path returned
# by the skill read. Run from the target repository or task worktree.
skill_file='<absolute-loaded-plugin-path>/skills/task-worktree/SKILL.md'
plugin_root=$(dirname "$(dirname "$(dirname "$skill_file")")")
helper="$plugin_root/scripts/ensure-worktrunk.sh"
if [ ! -r "$helper" ]; then
  printf 'Worktrunk helper is unavailable: %s\n' "$helper" >&2
  exit 1
fi
source "$helper" && ensure_worktrunk || exit 1
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

The primary-held designated-branch mapping is Claude-specific. Omp keeps its
ordinary single-branch identity and does not infer a second push branch.

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

**Omp does not relocate the live session when `wt` creates a worktree.**
Continue every task operation with the verified absolute task paths. For a
new task where a new process is useful, start one inside the task worktree:

```sh
wt switch --create <task-branch> --base <resolved-base> -x omp
```

The user may optionally move an idle existing session with `/move
<returned-path>`. Do not require that move for the explicit-path workflow.
Omp 18.5.0 has no direct supported relocation operation in its inspected
extension API; automatic plugin-driven relocation needs upstream API work and
is outside this task. Do not invoke Omp's built-in `/wt`: it has a separate
creation path, starts from current `HEAD`, and carries uncommitted changes.
The official Worktrunk Omp integration tracks activity only; it is not an
isolation mechanism and must not be duplicated here.

**File tools do not inherit a bash cwd change.** Omp resolves each `write`
target and each path in an `edit` payload against the session's own cwd. Use
the absolute task-worktree path in every file-tool target, including hashline
headers and move destinations; preserve the full path and snapshot tag returned
by `read`. Never retry a rejected primary mutation with the same relative path.

Set `cwd` to the task worktree on every later `bash` call. Pass absolute
task-worktree paths to `read`, `write`, `edit`, `glob`, and `grep`. Give the
same absolute path to a `task` handling a delegated slice. Verify registration
and branch with Worktrunk JSON and Git, then compare the primary status with its
setup baseline before delivery. Use `wt remove` for later manual cleanup, never
bare `git worktree remove`.
