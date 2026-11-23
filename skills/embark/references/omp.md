# Omp routes — embark

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md); [`codex.md`](codex.md) carries the same fallback as
this one, on a surface measured less.

**Omp has no session-opening client, so the web route has no calls here.** The
wave goes out through the harness-local subagent fallback `SKILL.md`'s
`Open the sessions` states, and the tables below are that fallback resolved to
Omp's surfaces. The absence of a session-opening client means the agent-driven
wave needs an owner turn; it does not mean supervised processes cannot survive
a client exit. The fallback exists for session work, not process supervision.

For an explicit Omp embark command, the initial identity read must be the
canonical single-issue `issue://` read. If the command supplied a GitHub URL,
preserve its repository in that `issue://` reference.
Read-only discovery and prerequisites may come first, but cannot certify this
step. The result supplies the canonical title, number, URL and labels. If its
metadata confirms the requested issue is an epic, set the orchestrator title
in the [`session-title` epic form](../../session-title/SKILL.md) before graph
traversal or any unrelated tool call. The extension denies dispatch and writes
before the identity read, then denies unrelated calls after the metadata
result; it cannot cancel calls already running in a batch. A free-form request
that invokes `embark` without an explicit command does not activate this
earlier barrier.

Only interactive or RPC user input activates or supersedes this barrier.
Plain `embark`, `/embark`, and `/skill:embark` commands each start a fresh
identity check, including a repeated command for the same issue. Timer
reminders, background results, and extension-origin input retain the current
state even when their text starts with `Embark #<number>`. Provider-turn
preparation is not a new user command.


The wave
========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Read the epic` | Read its identity before the graph | `read issue://<number>`; preserve an explicitly supplied repository-qualified issue reference |
| `Take the wave` | Read each eligible child's body and claim | `issue://<number>`, comments included |
| `Open the sessions` | Dispatch one implementor per eligible child, concurrently | `task`, one item per child issue in a single batch |
| `Open the sessions` | Name the implementor | the item's `name`, in `session-title`'s form |
| `Post the muster roll` | Comment on the epic | `daily_driver_gh_write({ args: ["issue", "comment", <number>, "--body-file", <path>] })` |
| `Post the muster roll` | Mark the wave in the epic's body | `daily_driver_gh_write({ args: ["issue", "edit", <number>, "--body-file", <path>] })` |

The wrapper appends and deduplicates provenance for both writes; submit the
body or comment without a new attribution block.


The dispatch is one batch, never one call per child: the items run
concurrently, and an item that fails to launch is reported in its own result
while the rest of the batch sails — the one-ship rule `SKILL.md` states,
delivered by the surface itself. The batch carries a shared `context` beside
its items, because the surface requires one, and it holds only what every
implementor needs: the repository, the base branch, and the fallback protocol
of `Open the sessions`. Issue scope stays in the issue; a summary of it in the
context is the second copy `SKILL.md` forbids.



The route an implementor runs
=============================

The `task` surface selects an `agent`, not a model. For mapped families, select
the agent named for the required class (`mechanical`, `routine`,
`intermediate`, `complex`, or `frontier`); each item sets only `agent`, with
no per-item model argument. Apply
[`issue-body`'s required-class policy](../../issue-body/references/omp.md#the-required-class).
`task.agentModelOverrides[agentName]` takes precedence over discovered agent
frontmatter, including tagged-role assignments such as `@routine` or
`@frontier`. Reviewer and scout specialization and host helper inference are
independent.

Record the required class, selected agent/effective route, and observed
execution model separately. Use `unreported` when execution identity is
unavailable; record an observed different model or fallback. `sonic` is a
bundled agent, not a model role.


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
| `Watch the wave` | Read subagent job state | The job IDs returned by `task`: `read proc://<job-id>` for status and `write proc://<job-id>/kill` to cancel |
| `Watch the wave` | Receive subagent results | `wait` with no arguments when blocked; results also auto-deliver |
| `Watch the wave` | Preserve a pull request CI watch | `review-cycle`'s persistent named Bash service |
| `Watch the wave` | Find a pull request for an issue when one exists | `issue://<number>` — `closed_by_pull_requests` |
| `Watch the wave` | Read a child issue's body and comments | `issue://<number>` |
| `Land the pull request` | Read draft, merge state, head SHA, labels, and body | `gh pr view <number> --json isDraft,mergeStateStatus,headRefOid,labels,body` |
| `Land the pull request` | Diagnose a blocked gate | `gh pr view <number> --json headRefOid,reviewDecision,statusCheckRollup`; current-head checks, statuses, and workflow runs through `review-cycle`'s `references/omp.md` |
| `Land the pull request` | Read review threads | `review-cycle`'s `references/omp.md` thread read |
| `Land the pull request` | Read submitted reviews, recorded review identifiers and SHAs, and dispositions | `review-cycle`'s `references/omp.md` review history read |
| `Land the pull request` | Read verification records | `gh api --paginate /repos/{owner}/{repo}/issues/{number}/comments` |
| `Land the pull request` | Read first-parent ancestry | `git show -s --format=%P <sha>` in a checkout containing the head and its ancestors; unavailable objects fail the predicate |
| `Land the pull request` | Squash merge the gated head | `gh pr merge <number> --squash --match-head-commit <headRefOid>` |
| `Close the epic` | Comment with the landed pull requests or missing claim | `daily_driver_gh_write({ args: ["issue", "comment", <number>, "--body-file", <path>] })` |
| `Close the epic` | Close as completed | `gh issue close <number> --reason completed` |

Apply `undertake`'s `Review evidence` predicate to the complete review,
conversation and thread histories and the gated `headRefOid`.

The merge is one conditional `gh pr merge` call for a task pull request after
the gate holds. `--match-head-commit <headRefOid>` makes it fail closed if the
task session pushes after the read.
`Close the epic` posts its evidence comment before `gh issue close`, and never
calls the latter when a child outcome is unsupported or landing is by hand.
Read the delivered outcome against the story's own completion contract: a
pull request for a task or bug, the evidenced answer recorded on the issue for
research.
An issue's closed state alone does not prove the epic outcome was met.

After the whole epic operation completes or reaches its evidenced by-hand
stopping point, and after cancelling the backstop and dropping subscriptions,
call `daily_driver_notify({ reason: "work_complete", key: "epic-complete",
message: "<epic outcome or by-hand action>" })`. Do not notify for a wave or
child completion. For a genuine unresolved human handoff, call
`daily_driver_notify({ reason: "attention_required", key: "<stable action key>",
message: "<specific action needed>" })` before the chat handoff. Choose a
stable key for the specific required action, not an attempt. Keys must be
nonblank and at most 160 characters; messages must be nonblank and at most
400 characters; neither may contain control characters or secrets. Child
agents report to the orchestrator, not the user. Recoverable errors, CI waits,
reminders, progress and ordinary final replies do not notify. Notifications
do not replace the record or chat handoff.


CI waiting uses `review-cycle`'s persistent named Bash service. Start the
service once, request `persist` through `write proc://<name>/mode`, and
confirm it with `read proc://<name>`. Do not pass `async` or `timeout` to
named-service mode. If persistence fails, stop the service and report the
failure; do not claim that CI remains watched.

This durability does not turn the process into an agent. A persistent service
can continue its bounded command after a client exits, but cannot reopen a
terminated owner. While the session is live, each implementor retains `pr`'s
owner reminder across renewable CI windows. An implementor result that says
only a detached service remains is unfinished, not an active agent watch.
Inspect its lifecycle and recover an ended owner on the same branch under
`Recovering an implementor`; do not wait for a user status request. Preserve
genuine prerequisites and avoid a second writer alongside a live owner.
After actual session shutdown, a later invocation must read the graph and
PR evidence; do not claim cross-shutdown recovery.

While the orchestrator lives, the backstop is the timer pair:
`daily_driver_schedule` arms it ten minutes out, and
`daily_driver_cancel_schedule` cancels it at the wave's close. The timer is
cleared on session shutdown. It supervises the live orchestrator only; the
persistent named CI service is stopped separately with
`write proc://<name>/kill`. The one-slot rule `SKILL.md` states still holds:
one timer, kept by the trigger id the call returned, filled again before the
turn ends while a wave is at sea.



The strong-model review
=======================

At each implementor's ready gate, the round is run by a strong model — the
orchestrator or the shared advisor, never the implementor. The implementor
hands its head over the messaging above and waits; the surface is
`review-cycle`'s own [`omp.md`](../../review-cycle/references/omp.md): native
Open Code Review (`ocr`), invoked as that file specifies. Its findings go back
to the implementor over the messaging above and are answered under the round's
protocol; the ready gate is `undertake`'s, and it is not satisfied until the
round on the head is.


Recovering an implementor
=========================

Address corrections to the subagent identifier through agent messaging. Read
its lifecycle using `proc://<job-id>`, cancel through
`proc://<job-id>/kill`, and dispatch a replacement through `task` under
`Recover a session`.
