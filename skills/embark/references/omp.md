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


The wave
========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Read the epic` | Read its identity before the graph | `read issue://<number>`; preserve an explicitly supplied repository-qualified issue reference |
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


The route an implementor runs
=============================

The `task` surface selects an `agent`, not a model. Select the agent named for
the task's required class (`mechanical`, `implementation`, `reasoning`, or
`frontier`). Each batch item sets only `agent`; it carries no per-item model
argument. Resolve the effective route under [`issue-body`'s required-class
policy](../../issue-body/references/omp.md#the-required-class):
`task.agentModelOverrides[agentName]` takes precedence over discovered agent
frontmatter, including a tagged-role assignment such as `@implementation` or
`@frontier`. Resolve configured prewalk and retry fallbacks under the same
eligibility requirements. Do not use `modelRoles.task` as a universal
implementor route.

Apply [`model-classes.md`'s selection policy](../../issue-body/references/model-classes.md#selection).
A current measured class outranks handwritten guidance, and a measured class
below the task's requirement excludes that route. A missing, `unmeasured`,
`unreported`, or stale row is unknown, not an automatic rejection; use the
operator's configured eligible preference without claiming measured
capability. That preference does not waive class, tools, context, modality,
availability, or credential requirements. Do not invent a freshness cutoff.

Reassess a visible parent-model authentication fallback or any other runtime
model mismatch before work continues. Never assume parent inheritance meets
the required class. Missing assignments, unavailable credentials, or
unsuitable effective routes stop only the affected task with a configuration
gap; launch the other eligible tasks in the single concurrent batch. Never
lower a class, alter shared roles, or restore a role the operator cleared to
make a wave launch.
Treat an effective astra/fable route as frontier, regardless of whether an
override, retry fallback, or visible parent inheritance selects it through
`reasoning` or another lower-class role. Classify the resolved selector rather
than its role label: the current `reasoning` default is
`openai-codex/gpt-6.1-sol:high`, not a frontier route.
An issue assigned `frontier` must include its explicit approval and exact
work envelope before dispatch. Reject an unauthorized frontier fallback
before the assignment starts; continue other tasks and report a configuration
gap if no eligible non-frontier route exists.

A frontier implementor receiving ordinary work performs only the bounded
routing and handoff to an eligible non-frontier class. Do not retain its
implementation or supervise it on frontier. Frontier implementation needs
separate, explicit user authorization for that exception and bounded scope;
frontier research approval is not enough.

Keep the required class, selected agent/effective route, and actual execution
model distinct in the muster roll. Record `unreported` when execution identity
is unavailable; a selector is not observed identity. If Omp reports a
different model or fallback, record that observed model and reassess before
work continues. `sonic` is a bundled agent, not a model role. Reviewers and
scouts are not implementation routes.


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
| `Watch the wave` | Find the pull request for a task issue | `issue://<number>` — `closed_by_pull_requests` |
| `Watch the wave` | Read a pull request's state and checks | `pr://<number>` |
| `Land the pull request` | Read draft, merge state, head SHA, labels, and body | `gh pr view <number> --json isDraft,mergeStateStatus,headRefOid,labels,body` |
| `Land the pull request` | Read review threads | `review-cycle`'s `references/omp.md` thread read |
| `Land the pull request` | Read the review-cycle completion notice | `gh pr view <number> --json headRefOid,comments` — `comments[].author.login` |
| `Land the pull request` | Read the commits after the notice's SHA | `git rev-list --first-parent --no-merges <sha>..<headRefOid>` after `git fetch` of the head |
| `Land the pull request` | Squash merge the gated head | `gh pr merge <number> --squash --match-head-commit <headRefOid>` |
| `Close the epic` | Comment with the landed pull requests or missing claim | `gh issue comment <number> --body-file <path>` |
| `Close the epic` | Close as completed | `gh issue close <number> --reason completed` |

`Land the pull request` uses the same readiness fields as `undertake`'s `The
milestone`: `isDraft` must be false, `mergeStateStatus` must be `CLEAN`, and
`headRefOid` is the head the merge binds to. The labels and body answer the
human-action read in the same call. The complete thread graph is the paginated
GraphQL read named by `review-cycle`; a REST comments page is not a substitute.

The completion read is the conversation-comment read `review-cycle`'s
`Review-cycle completion notice` names, read to the last page: the latest
comment starting with `## Review cycle complete! 🎉` whose author is the
author of the task issue's claim comment, and the SHA it names. Where that SHA is not
`headRefOid`, the named SHA must be on the head's first-parent chain
(`git rev-list --first-parent <headRefOid> | grep -qx <sha>`), and the
`rev-list` must print nothing. A SHA off that chain, or any printed commit,
fails the read.

The merge is one conditional `gh pr merge` call after the gate holds.
`--match-head-commit <headRefOid>` makes it fail closed if the task session
pushes after the read. `Close the epic` posts its evidence comment before
`gh issue close`, and never calls the latter when a `Summary` claim is missing
or landing is by hand.

**A live subagent's result or failure arrives as a wake of its own.** The
orchestrator ends its turn holding the job IDs returned by `task`, and each
implementor that finishes wakes it. Inspect a job without consuming delivery
with `read proc://<job-id>`; cancel it with `write proc://<job-id>/kill`. Use
`wait` with no arguments only when blocked. The GitHub state remains the
durable record: a task issue's pull request, checks, and review threads say
whether work is moving or stuck, and the epic graph says whether a task is
home.

CI waiting uses `review-cycle`'s persistent named Bash service. Start the
service once, request `persist` through `write proc://<name>/mode`, and
confirm it with `read proc://<name>`. Do not pass `async` or `timeout` to
named-service mode. If persistence fails, stop the service and report the
failure; do not claim that CI remains watched.

This durability does not turn the process into an agent. A persistent service
can continue its bounded CI command after the client exits, but it cannot
reopen or resume a terminated orchestrator, interpret the result, mark the
wave `done`, or launch the next wave. A later `embark` invocation must read the
graph and pull requests before continuing agent work.

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
