# Omp routes — embark

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md); [`codex.md`](codex.md) carries the same fallback as
this one, on a surface measured less.

**Omp has no session-opening client, so the web route has no calls here.** The
wave goes out through the harness-local subagent fallback `SKILL.md`'s
`Open the sessions` states, and the tables below are that fallback resolved to
Omp's surfaces. The absence of the client — and of the durable cross-session
wake, measured in `undertake`'s
[`omp.md`](../../undertake/references/omp.md) — is why the fallback exists,
not a reason to stop.

Reading the epic is ordinary issue work and needs nothing this file adds:
`epic`'s own [`omp.md`](../../epic/references/omp.md) has the issue reads, and
`issue-deps` has the graph.


The wave
========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Take the wave` | Read a task issue's body and claim | `issue://<number>`, comments included |
| `Open the sessions` | Dispatch one implementor per task, concurrently | `task`, one item per task issue in a single batch |
| `Open the sessions` | Name the implementor | the item's `name`, in `session-title`'s form |
| `Post the muster roll` | Comment on the epic | `gh issue comment <number> --body-file <path>` |
| `Post the muster roll` | Mark the wave in the epic's body | `gh issue edit <number> --body-file <path>` |

The dispatch is one batch, never one call per task: the items run
concurrently, and an item that fails to launch is reported in its own result
while the rest of the batch sails — the one-ship rule `SKILL.md` states,
delivered by the surface itself. The batch carries a shared `context` beside
its items, because the surface requires one, and it holds only what every
implementor needs: the repository, the base branch, and the fallback protocol
of `Open the sessions`. Task scope stays in the issue; a summary of it in the
context is the second copy `SKILL.md` forbids.

Duplicate-dispatch protection is unchanged: the epic's muster rolls and each
task issue's claim comments are read before the batch is built, exactly as
`Take the wave` words it.

Each item's prompt is the task issue number and the instruction to undertake
it, and nothing else. The prompt boundary of `Open the sessions` holds.


The model an implementor runs
=============================

The `task` surface selects an agent type, not a model identifier, and this
plugin ships no agents of its own. The cheaper default of `Open the sessions`
is therefore the default implementation agent type, made cheaper by the
harness's own task-role model configuration — and **what each implementor
actually ran on is read back from what the harness reports of that
subagent**, never recalled. Where that report names the orchestrator's own
model for a routine task, the muster roll records it as it is: a cheaper
default that configuration did not deliver is a configuration gap, reported
rather than papered over.

The task issue's `Model:` line is advisory here, exactly as `SKILL.md` says:
it is the judgement `epic` made, and the orchestrator reads it before
deciding whether the cheaper default is safe for this task. The bypass is
the orchestrator's judgement too, made the same way: dispatch a stronger
agent type for security-sensitive or unusually complex work — a stronger
subagent, never the orchestrator itself. Work too underspecified for any
subagent is a planning defect reported back into the task body, not a task
the orchestrator takes.


Asking for help
===============

**The messaging is the orchestrator's own agent messaging.** A subagent
inherits the orchestrator's identity on it, and a question it sends arrives as
steering; the orchestrator answers the same way. The advisor of
`Open the sessions` is the orchestrator itself by default. A shared strong
advisor is one further subagent dispatched once for the wave, addressed by the
identifier its dispatch returned — one advisor for the wave, never one per
task.


The watch
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Watch the wave` | Read the wave's live subagent state | the dispatch handles — `hub jobs` over them, `hub wait` to block on one |
| `Watch the wave` | Preserve a pull request CI watch | `review-cycle`'s persistent `hub start` route |
| `Watch the wave` | Find the pull request for a task issue | `issue://<number>` — `closed_by_pull_requests` |
| `Watch the wave` | Read a pull request's state and checks | `pr://<number>` |
| `Land the pull request` | Read draft, merge state, labels, and body | `gh pr view <number> --json isDraft,mergeStateStatus,labels,body` |
| `Land the pull request` | Read review threads | `review-cycle`'s `references/omp.md` thread read |
| `Land the pull request` | Squash merge | `gh pr merge <number> --squash` |
| `Close the epic` | Comment with the landed pull requests or missing claim | `gh issue comment <number> --body-file <path>` |
| `Close the epic` | Close as completed | `gh issue close <number> --reason completed` |

`Land the pull request` uses the same readiness fields as `undertake`'s `The
milestone`: `isDraft` must be false and `mergeStateStatus` must be `CLEAN`.
The labels and body answer the human-action read in the same call. The complete
thread graph is the paginated GraphQL read named by `review-cycle`; a REST
comments page is not a substitute.

The merge is one `gh pr merge <number> --squash` call after the gate holds.
`Close the epic` posts its evidence comment before `gh issue close`, and never
calls the latter when a `Summary` claim is missing or landing is by hand.

**A live subagent's result or failure arrives as a wake of its own.** The
orchestrator ends its turn holding the dispatch handles, and each implementor
that finishes wakes it. The GitHub state remains the durable record: a task
issue's pull request, checks, and review threads say whether work is moving or
stuck, and the epic graph says whether a task is home.

CI waiting uses `review-cycle`'s durable Hub process. `persist: true` keeps its
broker and watcher alive after the last Omp client exits. `detached: true`
would also survive broker shutdown and every Omp exit, but the bounded CI
watch does not use it. Hub keeps terminal completion owner-scoped and pending
while the orchestrator is absent. Resume the owning session in the same
project and reconnect to Hub to receive that completion, then read the pull
request state before acting. A different session can inspect the
project-scoped process by name but does not receive the owner's replay.

This durability does not turn the process into an agent. Hub cannot reopen or
resume a terminated orchestrator, interpret the completed watch, mark the wave
`done`, or launch the next wave. `daily_driver_schedule` also cannot supply
that autonomy: it is a managed timer cleared on session shutdown. If the
orchestrator terminates, process-only watches survive, but agent-driven wave
work resumes only when the owning session resumes or a later `embark`
invocation reads the graph and pull requests.

While the orchestrator lives, the backstop is the timer pair:
`daily_driver_schedule` arms it ten minutes out, and
`daily_driver_cancel_schedule` cancels it at the wave's close, when `Close the
epic` ends the check-ins and drops whatever watches ran under them — the
pull-request subscriptions on a surface that has them, the persistent Hub CI
watchers on this one. The one-slot rule `SKILL.md` states holds: one timer,
kept by the trigger id the call returned, filled again before the turn ends
while a wave is at sea.



The strong-model review
=======================

At each implementor's ready gate, the round is run by a strong model — the
orchestrator or the shared advisor, never the implementor. The implementor
hands its head over the messaging above and waits; the surface is
`review-cycle`'s own [`omp.md`](../../review-cycle/references/omp.md): the
`reviewer` task agent, dispatched through `task`. Its findings go back to the
implementor over the messaging above and are answered under the round's
protocol; the ready gate is `undertake`'s, and it is not satisfied until the
round on the head is.


Recovering an implementor
=========================

A correction is a message to the implementor's identifier. An implementor the
harness reports as failed, or as finished with no pull request across two
check-ins, is relaunched on the **same branch** — the claim comment
`undertake` posted on the task issue records it, and the open pull request's
head confirms it where one exists. The replacement is posted to the epic like
any other replacement, naming the subagent retired and the one that took
over.
