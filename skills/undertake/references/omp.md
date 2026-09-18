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
| `Read the issue and its edges` | Read the body, the graph and the comments | `issue://<number>`, comments included |
| `Read the issue and its edges` | Label an issue that carries none | `gh issue edit <number> --add-label task` |
| `Claim the issue` | Comment on the issue | `gh issue comment <number> -b "…"` |

**`issue://<number>` carries the comments**, so the read in that row is one
call and returns the handoff content `SKILL.md` asks for. Where a cache miss
or a truncated resource leaves them out, `gh issue view <number> --json
comments` is the read that returns them — the same call the readiness report
makes further down this file.

`issue-deps` owns the edge writes, and has its own routes. So does
`issue-labels`, whose `references/omp.md` says why `--add-label` needs no
read-first and the Claude route does.


The implementor
===============

No route, and that is the rule rather than a gap. `SKILL.md`'s `Implement`
owns it: the session running the sequence writes the code itself, so `task`
dispatches no implementor here. Omp has the route and it belongs to `embark`,
which uses it to run several task issues at once. The one dispatch inside this
sequence is `review-cycle`'s briefed subagent at `Verify the fix delta`, named
in that skill's own reference file.


The pull request
================

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the draft` | Open it | `pr`, which owns the call |
| `The gate` | Read the branch against its base | `gh pr view <number> --json mergeStateStatus` |
| `The gate` | Read CI on the head | `gh pr view <number> --json statusCheckRollup` |
| `The gate` | Read the review threads | `review-cycle`'s `references/omp.md` owns them |
| `Ready for review` | Take it out of draft | `gh pr ready <number>` |
| `Keep it current` | Merge the base branch in | `gh pr update-branch <number>` |
| `A round after ready goes back to draft` | Return it to draft | `gh pr ready <number> --undo` |
| `The milestone` | Read the readiness state | `gh pr view <number> --json isDraft,mergeable,mergeStateStatus,headRefOid` |
| `The milestone` | Read the existing comments | `gh pr view <number> --json comments` |
| `The milestone` | Post the report | `gh pr comment <number> --body-file <path>` |

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


The milestone
=============

`SKILL.md` owns what the report says and when it is owed; these are the calls
that read the readiness state, find the claim's timestamp, and post it.

**The readiness state is one read:**

    gh pr view <number> --json isDraft,mergeable,mergeStateStatus,headRefOid

`isDraft` false and `mergeable` `MERGEABLE` are two of the answers the report
needs, and neither is sufficient alone. `mergeStateStatus` answers the rest,
and here — after the draft is cleared — `CLEAN` is the only yes: `BEHIND` is
a base the branch does not carry, `UNSTABLE` a check that is no longer green,
`DIRTY` a conflict, and `UNKNOWN` and `BLOCKED` are states `SKILL.md` rules
out as readiness outright. Each is a wait, not a milestone. **`The gate` reads
the same field for less**, because a draft reports `DRAFT` or `BLOCKED` there
whatever its branch and checks are doing: only `BEHIND`, `DIRTY` and `UNKNOWN`
are that read's, and CI at the gate comes from `statusCheckRollup` instead.
`headRefOid` is the SHA the report binds to.

**The start is the claim comment's `createdAt`.** `issue://<issue>` carries
the comments, so `Read the issue and its edges` already has them; `gh issue
view <issue> --json comments` is the same read where that resource is not to
hand. The claim is the comment carrying the branch link and the `Model:` and
`session:` lines. Take its `createdAt`;
where more than one comment carries that shape, the earliest of them is the
start — a later claim does not restart the clock. A resumed session finds
the start with the read it makes anyway. An issue with no recoverable claim
leaves the timing `n/a`, per `SKILL.md`.

**The report posts as a pull-request comment** — a pull request's comments
are issue comments, so the write is the claim's own:

    gh pr comment <number> --body-file <path>

`--body-file` for the reason `Claim the issue`'s row gives: the report
carries backticks, a SHA, and timestamps, and a double-quoted shell argument
substitutes the backticks before `gh` sees them.

**Read the existing comments before posting** — `gh pr view <number> --json
comments` again, the report found by its opening line, `First-readiness
report`, the marker `SKILL.md` fixes; a resumed sequence that finds it posts
nothing.

**The provenance** comes from the sources `The session` names:
`daily_driver_get_session` for the model and the session id, the harness's
own statement of the serving model where the tool has none. The harness line
names Omp, with the version the harness itself reports — `omp --version`
where it answers. A version no surface in the session reports is `n/a`,
never a guessed one.


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
