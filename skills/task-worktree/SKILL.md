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

Worktrunk (`wt`) owns worktree creation and selection. If `wt` is unavailable,
stop and report that the Worktrunk CLI must be installed. Never fall back to
`git worktree add`, and never install software from a task-start hook.

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
   worktree's status. Keep the primary status as the baseline for the final
   check.
2. **Resolve the remote and base.** Use the remote declared by the task or
   repository, then `remote.pushDefault`, then the only configured remote.
   More than one unexplained remote is a stop. Use the task/repository base
   when declared; otherwise keep the full remote-tracking default branch name
   from `git symbolic-ref --short refs/remotes/<remote>/HEAD`. Never branch
   from whichever feature branch happens to be checked out.
3. **Choose one task identity.** Use the existing task branch from the task's
   record first, then the one branch designated by the harness. Otherwise use
   the project's branch convention, then a short name tied to the issue or
   task. A supplied task branch outranks a fresh harness designation.
4. **Inspect Worktrunk's worktrees.** Require `wt`, then run
   `wt --config-set 'list.json-schema=2' list --format=json`. Parse the JSON
   envelope's `.items[]`; identify the primary row by
   `.worktree.main == true`, and use `.worktree.path` for every path. Do not
   rely on output order, a guessed directory name, or rendered text.
   The schema override applies to this command only and does not rewrite user
   configuration.
5. **Reuse only the same task.** A registered worktree on the task branch may
   be reused only when the task record or this session identifies it as
   dedicated to this task. A branch belonging to another task is a collision,
   not permission to reuse it. Preserve branch and path collision inspection.
6. **Check effective placement before creation.** Run `wt config show` to read
   the config file locations and the project identifier. Inspect
   `WORKTRUNK_WORKTREE_PATH`, system/user `worktree-path` values, and the
   most-specific matching `[projects."<host>/<owner>/<repo>"]` setting in
   system/user config. If none sets it, use Worktrunk's documented default:
   `{{ repo_path }}/../{{ repo }}.{{ branch | sanitize }}`. Resolve the
   effective template for this repository and task branch before creation. Its
   path must be beside the primary worktree and outside every existing
   worktree. Stop with a clear explanation if placement conflicts with the
   policy; never overwrite the user's template, add a second one, or force a
   collision.
7. **Create or select with Worktrunk.** For a new task branch, run
   `wt switch --create <task-branch> --base <resolved-base> --no-cd
   --format=json`. For an existing free task branch, run
   `wt switch <task-branch> --no-cd --format=json`. Read `.path` from
   successful stdout JSON; stderr diagnostics are not a path. Quote every
   path, including paths with spaces. Do not use `--clobber`, `--yes`, or
   `--no-hooks`; preserve Worktrunk's normal hooks and approval behavior.
8. **Keep the detached-task exception.** When the current detached worktree is
   already dedicated to this task, attach it in place with `git switch
   <task-branch>` if that branch exists and is free, or `git switch -c
   <task-branch> <resolved-base>` otherwise. Worktrunk documents `git switch`
   for changing the branch of an existing worktree; this is not a fallback for
   worktree creation.
9. **Verify the boundary.** Verify the selected path is a registered worktree
   beside the primary path, and its checked-out branch is the task branch.
   Preserve the primary-checkout status baseline and do not copy any of its
   uncommitted changes.


Stay inside it
==============

After setup, every task read, search, edit, generated file, command, test, and
commit uses the task worktree as its root. A shell's current directory does not
carry across tool calls unless the harness says it does; set it on every call.
File tools use absolute task-worktree paths. Delegated prompts name the same
root explicitly.

Never edit, stage, clean, reset, stash, or commit in the primary worktree. Do
not copy the primary worktree's uncommitted files into the task worktree. They
are the user's work and are outside this task.

The task worktree persists through the pull request and review cycle. Cleanup
is not part of this skill. For later manual cleanup use `wt remove`, not bare
`git worktree remove`. Before delivery, compare the primary worktree with the
status recorded at setup. Report an external change; never erase it to make
the comparison pass.
