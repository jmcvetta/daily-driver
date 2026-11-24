---
name: task-worktree
description: >-
  Use before repository-changing work begins in a running session, before task
  research or the first mutating call, including when an investigation turns
  into edits. Supplies a dedicated registered non-primary worktree and a
  recoverable feature branch while the primary checkout stays unchanged.
  Not for read-only questions, investigations, or reviews. Reuse a worktree
  already dedicated to this task; attach a detached one before committing.
  A delegated slice uses its parent's task worktree.
---

# Task worktree

One repository-changing task gets one dedicated registered non-primary
worktree and one recoverable feature branch. The worktree is the task's
execution root, not only the place where edits land.

Use Git or the user's chosen worktree tool. Worktrunk is optional; do not
install it as an isolation prerequisite. Registration and ownership matter,
not the tool or sibling placement. A worktree is not a filesystem sandbox:
programs can still reach other checkouts and shared Git metadata.

**The execution routes differ by harness.** Read the reference for the harness
in use before the first repository read or change:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi, and
[`references/codex.md`](references/codex.md) for Codex.


The gate
========

Apply this skill before task research, not after the first edit.

- **A new repository-changing task needs a dedicated worktree.** This includes
  another skill whose workflow will change repository files.
- **A worktree already dedicated to this task is enough.** Reuse it. Detached
  non-primary file edits are allowed; attach a recoverable task branch before
  committing, without discarding existing changes.
- **A delegated slice of the same task does not create another task worktree.**
  Give it the parent's task-worktree path and keep its operations there.
- **Read-only work needs no isolation.** If an investigation or review turns
  into a request to change the repository, stop and establish the task
  worktree before researching or changing the new work.

This skill owns the task's branch identity and execution root. A workflow skill
that invokes it consumes both; it must not choose or cut another branch. The
skill establishes the task root but does not replace the workflow that owns
the task, issue, pull request, review, or dependency upgrade.


Establish the task root
=======================

1. **Inspect only the repository boundary.** Read the current repository root,
   branch, registered worktrees, and remote default branch.
2. **Resolve the remote and base.** Use the remote declared by the task or
   repository, then `remote.pushDefault`, then the only configured remote.
   More than one unexplained remote is a stop. Use the task/repository base
   when declared; otherwise keep the full remote-tracking default branch name
   from `git symbolic-ref --short refs/remotes/<remote>/HEAD`. Before creating
   a fresh task branch, fetch that base into its remote-tracking ref, where
   `<base-branch>` is `<resolved-base>` without its leading `<remote>/`:
   `git fetch <remote> +refs/heads/<base-branch>:refs/remotes/<remote>/<base-branch>`.
   A failed fetch stops creation; never silently use the stale local ref.
   Never branch from whichever feature branch happens to be checked out.
3. **Choose the task identities.** A recorded resume branch has precedence.
   Otherwise use exactly one branch designated by the harness, then its
   documented naming convention. Multiple designations are a collision.
   The harness reference owns any primary-held designation exception:
   retain the designated remote push identity but use a separate local
   execution branch. Never move or attach the primary branch elsewhere.
4. **Inspect registered worktrees.** Run `git worktree list --porcelain -z`.
   Parse NUL-delimited fields and records, including paths with spaces;
   the first record identifies the primary. Record each path, branch,
   detached state, and locked or prunable marker. Do not use a guessed path
   or rendered columns. A stale or locked record is not a free destination.
5. **Reuse only the same task.** Reuse a registered worktree only when the
   task record or this session identifies it as dedicated to this task.
   Another task's branch or worktree is a collision. Coordinate one writer
   per task worktree and branch; include shared-ref operations in that
   coordination. A clean worktree alone does not establish ownership.
6. **Choose a safe path.** Use the user's configured placement or an explicit
   unused path. External worktrees are allowed. Reject paths inside the
   primary or another worktree, including symlink-resolved overlap, and
   occupied destinations. Do not overwrite a path or change user configuration
   to make it fit. An existing nested repository keeps its own primary;
   never treat its files as ordinary feature-worktree files.
7. **Create or select the task worktree.** Use Git or the user's chosen tool
   with an explicit base. For a task-record branch, first fetch its exact ref:
   `git fetch <remote> +refs/heads/<task-branch>:refs/remotes/<remote>/<task-branch>`.
   If the local branch does not exist, use
   `git worktree add --track -b <task-branch> <task-path> <remote>/<task-branch>`.
   If it exists and is free, use `git worktree add <task-path> <task-branch>`;
   if already registered for this task, use that registered path directly.
   Advance a resumed branch only with `git merge --ff-only
   <remote>/<task-branch>` inside its worktree. A failed fast-forward is a
   collision to inspect; never recreate the branch from the base.
   For a fresh branch use `git worktree add -b <task-branch> <task-path>
   <resolved-base>`. For an existing local task branch with no remote task
   branch, use `git worktree add <task-path> <task-branch>`.

   Preserve the chosen tool's hooks and approval rules. Do not force branch
   reuse, discard changes, skip hooks, or bypass a trust decision.

   In the primary-held designation exception, use a distinct short issue-based
   local execution branch and create it from the resolved remote default base,
   never from the primary checkout's `HEAD`. Before using the designated
   remote push branch, inspect its remote tip and the task record. An existing
   unrelated head is a collision; never overwrite it. Push from the task
   worktree with the explicit, non-force refspec
   `git push -u <remote> <execution-branch>:<designated-branch>`. Keep the
   local execution branch and remote push branch as separate identities for
   every later push, PR lookup, CI read, and claim. Normal non-fast-forward
   protection remains in force.
   Quote every path, including paths with spaces.
8. **Recover a detached task branch before committing.** A detached
   non-primary worktree dedicated to this task may be edited. Before a
   commit, inspect branch/path ownership and preserve its current HEAD and
   changes. For a fresh recovery branch, use
   `git switch -c <task-branch>` at that HEAD, not at the default base.
   For a recorded existing branch, attach only after confirming it names the
   detached HEAD and is not held elsewhere; otherwise inspect the divergence
   without switching, resetting, stashing, copying, or overwriting work.
   Fetch remote-only recovery branches by their exact ref first. Do not move
   detached task commits to the base or silently abandon them.


Stay inside it
==============

After setup, every task read, search, edit, generated file, command, test, and
commit uses the task worktree as its root. A shell's current directory does not
carry across tool calls unless the harness says it does; set it on every call.
File tools use absolute task-worktree paths. Delegated prompts name the same
root explicitly.

Never edit, stage, clean, reset, stash, or commit in the primary worktree. Do
not copy its uncommitted files into the task worktree. Pre-existing and
unrelated user changes stay outside the task commit.

The task worktree persists through the pull request and review cycle. Cleanup
is not part of this skill. Later manual cleanup may use Git or the user's
