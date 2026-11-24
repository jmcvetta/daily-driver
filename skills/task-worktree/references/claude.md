# Claude Code routes — task-worktree

`SKILL.md` names the operations. This file names how a Claude Code session
performs them. Oh My Pi's route is in [`omp.md`](omp.md), and Codex's in
[`codex.md`](codex.md).

Use `Bash` for the Git commands in `SKILL.md`. Git or the user's chosen tool
may create the dedicated registered non-primary worktree. Worktrunk is
optional; neither installation nor sibling placement is required.

```sh
git rev-parse --show-toplevel
git branch --show-current
git remote
git config --get remote.pushDefault
git symbolic-ref --short refs/remotes/<remote>/HEAD
git worktree list --porcelain -z
git fetch <remote> +refs/heads/<base-branch>:refs/remotes/<remote>/<base-branch>
git worktree add -b <task-branch> <task-path> <resolved-base>
```

Use the task record's branch before a new designation; otherwise use exactly
one designated branch, then the project convention or a short issue-based
name. Parse Git's NUL-delimited registration records; the first is the primary.
Verify canonical non-overlap, task ownership, and branch/path collisions.
External worktrees and paths with spaces are valid.

**A designated branch held by the primary has one narrow route.** Only for
new work with no resume branch, read
`session_context.outcomes[].git_repository.git_info` for the target repository.
Require exactly one designation and confirm that same branch appears in
Git's primary record. Its repository is the push repository; do not use
`external_metadata.current_branches` as designation evidence. Never move,
edit or attach the primary branch.

Choose a separate short issue-based execution branch and create it with
`git worktree add -b <execution-branch> <task-path> <resolved-base>`.
Inspect local branch, path and remote designated-ref collisions. The fresh
execution branch starts at the remote default base, excluding primary-only
commits and files. An unrelated existing remote head is a collision.
Push only with `git push -u <remote> <execution-branch>:<designated-branch>`,
without force. Keep local execution and remote/PR head identities separate;
do not create another remote branch or PR for the local name.

For a recorded remote branch, fetch its exact ref first. A remote-only branch
uses `git worktree add --track -b <task-branch> <task-path>
<remote>/<task-branch>`. An existing free local branch uses
`git worktree add <task-path> <task-branch>`. A registered same-task worktree
is reused directly. Advance a resumed branch with `git merge --ff-only
<remote>/<task-branch>` inside it; inspect a failed fast-forward as a collision.
Do not recreate it from the base.

Preserve hooks and trust decisions for the chosen tool. The official
Worktrunk `WorktreeCreate` hook omits this procedure's explicit base; do not
assume that hook enforces the resolved task base or override it.

A detached non-primary task worktree may be edited. Before committing, create
a recovery branch at its current HEAD with `git switch -c <task-branch>`.
For an existing recorded branch, confirm its tip equals that HEAD and is free
before attaching. Never switch away from unrelated changes or abandon commits.

`Bash` does not relocate the session. Prefix each later shell command with
`cd <task-worktree> &&`, or use its directory option. Use absolute task paths
with `Read`, `Write`, `Edit`, `Glob` and `Grep`; give delegated slices the same
root. Coordinate shared-ref and same-worktree writers; never make ordinary
commits to `master`. Preserve the primary worktree; keep pre-existing and
unrelated user changes outside the task commit.
