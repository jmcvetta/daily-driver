# Codex routes — undertake

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in
[`claude.md`](claude.md), Oh My Pi's in [`omp.md`](omp.md).

**Codex has no GitHub tool of its own** — no `mcp__github__*` server, and no
built-in `github` tool with an `issue://` or `pr://` cache behind it. There is
one client, `gh` in the shell.


The issue
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the issue` | Search the open issues | `gh search issues` |
| `Open the issue` | Open one, labelled | `gh issue create --label task` |
| `Read the issue and its edges` | Read the body, the graph and the comments | `gh issue view <number> --json body,labels,comments,blockedBy,subIssues,parent` |
| `Read the issue and its edges` | Label an issue that carries none | `gh issue edit <number> --add-label task` |
| `Claim the issue` | Comment on the issue | `gh issue comment <number> --body-file <path>` |

`--body-file` rather than `-b`: the claim carries backticks and markdown
links, and a double-quoted shell argument substitutes the backticks before
`gh` sees them. `pr-body`'s [`codex.md`](../../pr-body/references/codex.md)
makes the same argument at length.

`comments` is in that field list because `Claim the issue` needs it: a claim
already on the issue is what says the sequence is being re-entered, or that
another session got there first. A read without it cannot tell either.

The `--json` fields in the read row need `gh` at its stated floor.
`issue-deps` owns the edge reads and picks its own client — two clients here
rather than three — so read that skill's routes before believing an empty
answer. So does `issue-labels`, whose `references/codex.md` says why
`--add-label` needs no read-first and the Claude route does.


The pull request
================

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the draft` | Open it | `pr`, which owns the call |
| `Ready for review` | Take it out of draft | `gh pr ready <number>` |
| `Keep it current` | Merge the base branch in | `gh pr update-branch <number>` |
| `A round after ready goes back to draft` | Return it to draft | `gh pr ready <number> --undo` |

`Review the head`, `Fix, answer, resolve, push`, and `Verify the fix delta` are
`review-cycle`'s. Its `references/codex.md` names the full-review surface and
the unavailable-delta stop that keeps the pull request draft.


The session
===========

**Codex exposes no session id, so the claim records `session: n/a`** — the
marker `SKILL.md` prescribes, not a diagnostic about the missing surface. The
`Model:` line repeats what the harness states is serving the turn — the
session's configured model — rather than a recalled name.

The branch comes from the task worktree's Git state:
`git branch --show-current` runs in that worktree. `OWNER/REPO` for the branch
link comes from the remote `task-worktree` resolved, never from an assumed
`origin`.


There is no durable wake
========================

**No wake on this harness is known to outlive the turn that armed it**, so
`Keep it current`'s cadence does not run here. After `Ready for review`, say
once that the watch is the catch-up look below, and stop.

**The catch-up look is the first read of every turn that lands back on the
pull request.** A turn that returns the session to the pull request — a
resume, a continuation, a user turn about it — starts with the base-currency
read, before anything else the turn was going to do:

    gh pr view <number> --json mergeStateStatus,mergeable

`BEHIND` runs `gh pr update-branch <number>` — `Keep it current`'s merge —
before the turn continues; `DIRTY` is the conflict stop `SKILL.md` writes
under `Where it stops and waits`; `CLEAN`, `DRAFT` and `UNSTABLE` need
nothing. `BLOCKED` and an indeterminate answer are not currency answers: run
the update-branch call anyway, whose own "already up to date" reply settles
what this read has not.

This is the Omp answer arrived at for a different reason. Omp has a timer and
it is measured to die with the session; Codex has no timer this plugin has
found at all. Either way `SKILL.md`'s own rule applies — a watch a surface
cannot keep is worse claimed than skipped — and the never-empty wake slot,
[`0010`](../../../docs/notes/0010-the-wake-slot-is-never-empty.md), is the
Claude Code rule this harness does not carry.
