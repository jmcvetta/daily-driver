---
name: task-worktree
description: >-
  This skill should be used before repository-changing work begins in an
  already-running Claude Code, Codex, or Oh My Pi session — including when the
  user asks to implement, build, fix, refactor, write, or update repository
  files; assigns an issue; invokes a workflow that will change the repository;
  or when a read-only investigation turns into edits. It fires before task
  research or the first mutating call. Supplies the feature branch from the
  repository's base branch, the sibling worktree, and the rule that every later
  task operation stays rooted there while the primary worktree stays unchanged.
  Not for read-only questions, investigations, or reviews. Not when the current
  worktree is already dedicated to this task and attached to its feature
  branch; a detached task worktree still triggers it. A delegated slice uses
  its parent's task worktree and does not create another one.
---

# Task worktree

One repository-changing task gets one feature branch and one sibling worktree.
The worktree is the task's execution root, not only the place where edits land.

This is model-directed workflow. No supported harness can create a worktree and
atomically relocate an already-running session into it. The boundary therefore
holds only when every later tool call names or enters the task worktree.

**The execution routes differ by harness.** Read the reference for the harness
in use before the first repository read or change:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi, and
[`references/codex.md`](references/codex.md) for Codex.


The gate
========

Apply this skill before task research, not after the first edit.

- **A new repository-changing task needs isolation.** This includes another
  skill whose workflow will change repository files.
- **A worktree already dedicated and attached to this task branch is enough.**
  Reuse it. A detached task worktree still needs this skill so it gets a
  feature branch before work continues.
- **A delegated slice of the same task does not create another task worktree.**
  Give it the parent's task-worktree path and keep its operations there.
- **Read-only work needs no isolation.** If an investigation or review turns
  into a request to change the repository, stop and establish the task
  worktree before researching or changing the new work.

This skill owns the task's branch identity and execution root. A workflow skill
that invokes it consumes both; it must not choose or cut another branch. The
skill establishes isolation but does not replace the workflow that owns the
task, issue, pull request, review, or dependency upgrade.


Establish the task root
=======================

1. **Inspect only the repository boundary.** Read the current repository root,
   branch, registered worktrees, remote default branch, and the primary
   worktree's status. This setup inspection is not task research. Keep the
   primary status as the baseline for the final check.
2. **Resolve the base branch.** Use the base declared by the task or repository;
   otherwise use the remote's default branch. Never branch from whatever
   happens to be checked out. If neither source identifies a base, ask rather
   than guess.
3. **Choose one task identity.** Use the one feature branch the harness already
   designated for this task, when it designated exactly one. Otherwise use the
   project's branch convention, then a short name tied to the issue or task.
   Derive the worktree directory from the same identity. Put it beside the
   primary worktree, never inside any existing worktree.
4. **Reuse only the same task.** A current linked worktree and attached branch
   satisfy the rule only when they are already dedicated to this task. In a
   detached task worktree, attach the existing task branch when it is free, or
   create it from the resolved base when it does not exist. Do not mistake an
   unrelated linked worktree for permission to reuse it.
5. **Otherwise create the branch and worktree together.** If the task branch
   already exists from an earlier run, attach that branch instead of creating
   a second branch. Stop on a branch or path collision; inspect it before
   deciding whether it belongs to this task.
6. **Verify the boundary.** The task path must be a registered worktree beside
   the primary path, and its checked-out branch must be the task branch.


Stay inside it
==============

After setup, every task read, search, edit, generated file, command, test, and
commit uses the task worktree as its root. A shell's current directory does not
carry across tool calls unless the harness says it does; set it on every call.
File tools use paths rooted at the task worktree. Delegated prompts name the
same root explicitly.

Never edit, stage, clean, reset, stash, or commit in the primary worktree. Do
not copy the primary worktree's uncommitted files into the task worktree. They
are the user's work and are outside this task.

The task worktree persists through the pull request and review cycle. Cleanup
is not part of this skill. Before delivery, compare the primary worktree with
the status recorded at setup. Report an external change; never erase it to make
the comparison pass.
