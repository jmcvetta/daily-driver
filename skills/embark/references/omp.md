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
agent type for security-sensitive or unusually complex work, or take the
task itself.


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
| `Watch the wave` | Read the wave's state | the dispatch handles — `hub jobs` over them, `hub wait` to block on one |
| `Watch the wave` | Find the pull request for a task issue | `issue://<number>` — `closed_by_pull_requests` |
| `Watch the wave` | Read a pull request's state and checks | `pr://<number>` |

**A subagent's result — or failure — arrives as a wake of its own**, so the
wave needs no session client and no durable timer to be supervised: the
orchestrator ends its turn holding the handles, and each implementor that
finishes wakes it. That is what `SKILL.md` means by supervising the wave
through the harness's subagent lifecycle, and it is why the missing durable
wake is not a stop here.

**The GitHub watch runs on top of it, unchanged.** A task issue's pull
request, its checks and its review threads are still how work in progress is
told from work stuck, and the epic's graph is still how a task being home is
read. `Take the wave`'s three empty-batch answers read the same graph.

**The lifecycle ends where the implementors finish.** A subagent's completion
wake is spent by then and its pull request is still open; where the surface
delivers no pull-request event and holds no durable timer, the close of the
wave — the wave marked `done`, the next one launched — is resumed by the next
`embark` invocation, and that is said once rather than claimed as a watch.


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
