# Codex routes — pr

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in
[`claude.md`](claude.md), Oh My Pi's in [`omp.md`](omp.md).

**Codex has no GitHub tool of its own** — no `mcp__github__*` server and no
built-in `github` tool. Every call below is `gh` in the shell, which is the
half of the Omp routes that carries over unchanged.

- **Checking whether a pull request already exists for the branch.**
  `gh pr view` (or `gh pr list --head <branch>`) finds it.
- **Opening a new pull request.** `gh pr create --draft`, for the initial
  state this skill requires.
- **Updating an existing pull request as a whole** — title and body
  together. `gh pr edit`, called once both are decided (`pr-title`,
  `pr-body`).
 
Keep it current
===============

Start this route immediately after creating or editing a PR and on every
owner turn that returns to it. Codex has no durable wake, process, or
subscription; do not claim autonomous maintenance.

Read:

    gh pr view <number> --json state,mergeStateStatus,mergeable,headRefOid,statusCheckRollup

If the PR is merged or closed, or the user has stopped the watch, exit before
any update. Before a currency update, read both check and status endpoints via
`review-cycle`; defer the update if either reports a run in flight. For
`BEHIND`, `DRAFT`, `BLOCKED`, or an indeterminate merge state, run `gh pr
update-branch <number>`. `DIRTY` is a conflict stop; `CLEAN` and `UNSTABLE`
need no update.

After an update that can move the head, read `gh pr view <number> --json
headRefOid,statusCheckRollup` and both check and status endpoints again.
Pending checks use `review-cycle`'s bounded wait. There is no timer or
subscription to cancel when the watch stops.
