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


The implementor
===============

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Implement` | Dispatch the implementor subagent | `task`, one subagent per undertaking |

`SKILL.md`'s `Implement` owns the rule: delegation is unconditional on a
surface that has the route, and the orchestrator keeps responsibility for
claim, pull request, watch and gates. Omp has the route.


The pull request
================

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the draft` | Open it | `pr`, which owns the call |
| `Ready for review` | Take it out of draft | `gh pr ready <number>` |
| `Keep it current` | Merge the base branch in | `gh pr update-branch <number>` |
| `A round after ready goes back to draft` | Return it to draft | `gh pr ready <number> --undo` |

`Review the head`, `Fix, answer, resolve, push`, and `Verify the fix delta` are
`review-cycle`'s. Its `references/omp.md` names the reviewer task, durable
record, and bounded delta-pass contract.


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


Process durability does not run the cadence
===========================================

**`daily_driver_schedule` is an in-process managed timer.** Managed timers are
unref'd and cleared on `session_shutdown`, so a reminder dies with the
session. Use it for `Keep it current` check-ins only while this session
remains alive. **Its pair is `daily_driver_cancel_schedule`.** The one-timer
rule `SKILL.md` states holds while the timer lives: a CI wait that borrows the
wake slot cancels the check-in with `daily_driver_cancel_schedule` and re-arms
it after, and each of the three exits — pull request merged or closed, or the
user says to stop — cancels it too, so nothing fires into a turn that no
longer wants it.

Hub supplies a different guarantee. A process started with `persist: true`
survives the last Omp client exiting. `detached: true` also survives broker
shutdown and every Omp exit. Terminal completion is owner-scoped and remains
pending until the owning session resumes in the same project and reconnects
to Hub. This is the durable route for the bounded CI watcher in
`review-cycle`'s [`omp.md`](../../review-cycle/references/omp.md).

**Hub does not launch or resume the agent that runs `Keep it current`.** The
cadence must inspect CI, decide whether an update is safe, call `gh pr
update-branch <number>`, and apply the ready gate. A supervised process can
preserve a watch and replay its completion. It cannot perform those agent
turns after the session terminates.

After `Ready for review`, use `daily_driver_schedule` for the next check-in
while the session is live. Each CI wait uses the persistent Hub watcher. If
the owning session terminates, the cadence pauses, but an existing watcher and
its completion do not disappear. A different session can inspect the
project-scoped process by name, but the owner's completion is not delivered
to it.
Each CI wait borrows the wake slot while it runs: cancel the live check-in
with `daily_driver_cancel_schedule` before `hub wait`, and re-arm it with
`daily_driver_schedule` once the wait's reads are done.

The catch-up look
-----------------

**The first read of every turn that lands back on the pull request is the
base-currency read.** Omp has no durable wake, so a session that has come
back is the only agent that will ever notice the base moved. The turn that
resumes the owning session, reconnects to Hub, replays a pending completion,
or simply returns to the pull request on a user turn starts with:

    gh pr view <number> --json mergeStateStatus,mergeable

| `mergeStateStatus` | Meaning | Move |
| ------------------ | ------- | ---- |
| `BEHIND` | the base moved; the branch does not conflict | `gh pr update-branch <number>` — `Keep it current`'s merge — then continue the turn |
| `DIRTY` | the branch conflicts with the base | the conflict stop `SKILL.md` writes under `Where it stops and waits` |
| `CLEAN`, `DRAFT`, `UNSTABLE` | current, or held by draft state or checks | nothing; continue the turn |
| `BLOCKED`, `UNKNOWN` | not a currency answer: required reviews, or a state GitHub cannot currently determine | the update-branch call anyway — it is the test as well as the merge, and its own "already up to date" answer settles currency where this read has not; a call that fails changes nothing and reaches the conflict stop |

The read is the look; the update-branch call is the merge. The call's own
"already up to date" answer cannot stand in for the read, because something
must decide to make the call — and a `DIRTY` answer must reach the stop
rather than a failed merge. The resumed-owner order is: reconnect to Hub,
consume any pending completion, take this read, then the CI reads the
completion was replayed for, then arm the next live-session check-in.

This is the Omp boundary: managed timers are session-local; Hub processes and
their owner-scoped completions are durable; autonomous base synchronization
still needs a running agent session.
