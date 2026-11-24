# Oh My Pi routes — task-worktree

`SKILL.md` names the operations. This file names how an Oh My Pi session
performs them. Claude Code's route is in [`claude.md`](claude.md), and Codex's
in [`codex.md`](codex.md).

Use `bash` for the Git commands in `SKILL.md`. Git is sufficient; Worktrunk
or the user's chosen tool may create the same registered worktree without
installation or a placement override.

```sh
git rev-parse --show-toplevel
git branch --show-current
git remote
git config --get remote.pushDefault
git symbolic-ref --short refs/remotes/<remote>/HEAD
git worktree list --porcelain -z
git fetch <remote> +refs/heads/<base-branch>:refs/remotes/<remote>/<base-branch>
git -C <primary-worktree> status --short
# Fresh task branch; select an unused, non-overlapping task path.
git worktree add -b <task-branch> <task-path> <resolved-base>
# Resume a recorded remote-only task branch.
git fetch <remote> +refs/heads/<task-branch>:refs/remotes/<remote>/<task-branch>
git worktree add --track -b <task-branch> <task-path> <remote>/<task-branch>
# An existing free branch, or a registered same-task worktree, is reused.
git worktree add <task-path> <task-branch>
git -C <task-path> merge --ff-only <remote>/<task-branch>
```

These are alternative creation routes, not a sequence to run all at once.
Use the task record's branch before a new designation. Otherwise use exactly
one designated branch, then the project convention or a short issue-based
name. Omp keeps one local/remote branch identity; the primary-held
designation exception is Claude-specific.

Parse Git's NUL-delimited registration records, not whitespace-separated
columns. The first record is the primary. Verify the selected path's
registration, non-primary identity, canonical non-overlap and task ownership.
External worktrees and paths with spaces are supported. Do not force branch
reuse or touch an occupied path.

A detached non-primary worktree dedicated to this task permits file edits.
Before committing, recover at its current HEAD with
`git switch -c <task-branch>` in that worktree. For an existing recorded branch,
first confirm its tip equals the detached HEAD and it is not held elsewhere.
Inspect divergence without discarding commits or unrelated changes.

**Creating a worktree does not relocate the live Omp session.** Continue
with the verified absolute task paths. For a new process, launch `omp --cwd
<task-path>` inside the selected task worktree. The user may optionally move
an idle session with `/move <task-path>`; do not require that move for the
explicit-path workflow. Do not invoke Omp's built-in `/wt`: its separate
creation route starts from current `HEAD` and carries uncommitted changes.
The official Worktrunk integration tracks activity, not isolation.

**File tools do not inherit a bash cwd change.** Use the absolute task path
in every `write` target, `edit` header and move destination, preserving the
snapshot tag from `read`. Set `cwd` on every `bash` call and use absolute
task paths with `read`, `glob` and `grep`. Give delegated slices that same
root. Never retry a rejected primary mutation with the same relative path.

The current guard keeps canonical file-target diagnostics and primary Git
rewrite checks, including detached-primary protection. Its global shell
recognizer still refuses opaque executable expansion and nonliteral `eval`.
It is not a filesystem sandbox; scripts, eval kernels and extension code can
reach other paths. See the actual-route evidence and unmet integration in
[`docs/harness-integration.md`](../../../docs/harness-integration.md#worktree-containment-integration-gap).
Do not remove those checks until an equivalent boundary is active and proven.

Coordinate concurrent writers, including shared refs. Do not make ordinary
commits to `master`. Compare the primary status with its setup baseline
before delivery; report external changes without undoing them.
