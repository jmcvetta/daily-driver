# Omp routes — undertake

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).

Two clients share the work. The built-in `github` tool reads and writes what it
covers; `gh` covers the rest, and every read is also available as an `issue://`
or `pr://` internal URL, which resolves from the same cache the `github` tool
writes to.


The issue
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the issue` | Search the open issues | `github.search_issues`, or `gh search issues` |
| `Open the issue` | Open one, labelled | `gh issue create --label task` |
| `Read the issue and its edges` | Read the body and the graph | `issue://<number>` |
| `Read the issue and its edges` | Label an issue that carries none | `gh issue edit <number> --add-label task` |
| `Claim the issue` | Comment on the issue | `gh issue comment <number> -b "…"` |

`issue-deps` owns the edge writes, and has its own routes. So does
`issue-labels`, whose `references/omp.md` says why `--add-label` needs no
read-first and the Claude route does.


The pull request
================

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the draft` | Open it | `pr`, which owns the call |
| `Ready for review` | Take it out of draft | `gh pr ready <number>` |
| `Keep it current` | Merge the base branch in | `gh pr update-branch <number>` |
| `A round after ready goes back to draft` | Return it to draft | `gh pr ready <number> --undo` |

Reading a pull request is `pr://<number>`. `Review the head` and `Fix, answer,
resolve, push` are `review-cycle`'s, and its own `references/omp.md` has the
review surface, the wait and the thread clients.


The session
===========

**The claim reads the model and the session id from
`daily_driver_get_session`**, the tool `extensions/daily-driver.js` registers.
It answers this session's own id (`ctx.sessionManager.getSessionId()`), its
name, and the id of the model serving it. The claim records both verbatim —
`Model: <model>` and `session: <id>`, one line each, no note about where the
values came from. Omp has no web URL for a session, so the id goes in bare
rather than linked.

The branch comes from the task worktree's Git state:
`git branch --show-current` runs in that worktree. `OWNER/REPO` for the branch
link comes from the remote `task-worktree` resolved, never from an assumed
`origin`.


There is no durable wake
========================

**`daily_driver_schedule` is an in-process managed timer.** Omp's own
documentation says managed timers are unref'd and cleared on
`session_shutdown`, so a reminder dies with the session. It is not a
`send_later`, which survives the session that armed it.

So **`Keep it current`'s cadence does not run on this harness.** After
`Ready for review`, say once that the branch is kept current by the next Omp
session that picks the pull request up, and stop. `daily_driver_schedule` is
for a follow-up inside the current session, never for a watch meant to outlive
it.

The never-empty wake slot —
[`0010`](../../../docs/notes/0010-the-wake-slot-is-never-empty.md) — is
therefore the Claude rule this harness does not carry. It is recorded here so
that a reader who finds it cited in `SKILL.md` knows why it does not bind, and
so that a durable wake arriving in Omp later has a decision to be measured
against.
