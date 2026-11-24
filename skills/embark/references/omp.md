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

For an explicit Omp embark command, read the requested issue before dispatch:
use the single-issue `issue://` read, or `gh issue view <number> --repo
<owner>/<repo> --json number,title,url,labels`. Preserve any explicitly
supplied repository. The successful result supplies the title, number, URL and
labels. If it confirms an epic or discovery, set the orchestrator title in the
[`session-title` epic form](../../session-title/SKILL.md) before dispatch or
claims. Read-only research and diagnostics remain available while identity or
title recovery is pending; they do not release the barrier. A free-form
request without an explicit command does not activate this barrier.

Only interactive or RPC user input activates or supersedes this barrier.
Plain `embark`, `/embark`, and `/skill:embark` commands each start a fresh
identity check, including a repeated command for the same issue. Timer
reminders, background results, and extension-origin input retain the current
state even when their text starts with `Embark #<number>`. Provider-turn
preparation is not a new user command.

Recovering the startup barrier
=============================

While identity or title recovery is pending, dispatch and issue claims remain
blocked. Independent research, diagnostics, and other work remain subject to
their ordinary guards. Reporting a defect does not satisfy the title barrier;
use the normal attributed reporting routes. After the authoritative issue
read, set the title using [`session-title`](../../session-title/references/omp.md).


The wave
========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Read the epic` | Read its identity before dispatch | `read issue://<number>` or the structured `gh issue view` form above |
| `Take the wave` | Read each eligible child's body and claim | `issue://<number>`, comments included |
| `Open the sessions` | Dispatch one implementor per eligible child, concurrently | `task`, one item per child issue in a single batch |
| `Open the sessions` | Name the implementor | the item's `name`, in `session-title`'s form |
| `Post the muster roll` | Comment on the epic | `daily_driver_gh_write({ args: ["issue", "comment", <number>, "--body-file", <path>] })` |

The wrapper appends and deduplicates provenance for the comment; submit it
without a new attribution block.


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

The `task` surface selects an `agent`, not a model. Select
the agent named for the required class (`mechanical`, `routine`,
`intermediate`, `complex`, or `frontier`); each item sets only `agent`, with
no per-item model argument. The implementor attempts its effective Omp class
role once; a missing or failed selection explains and continues, not admission.
Apply
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
| `Land the pull request` | Read relevant review evidence and finding dispositions | `review-cycle`'s `references/omp.md` review and conversation routes |
| `Land the pull request` | Squash merge the gated head | Prepare the paginated source messages and call `gh pr merge <number> --squash --body-file <path> --match-head-commit <headRefOid>` as below |
| `Close the epic` | Comment with the landed pull requests or missing claim | `daily_driver_gh_write({ args: ["issue", "comment", <number>, "--body-file", <path>] })` |
| `Close the epic` | Close as completed | `gh issue close <number> --reason completed` |

Apply `undertake`'s `Review evidence` predicate to the relevant records and
the gated `headRefOid`; read more history only when needed to establish it.

When the gate holds and landing is authorized, prepare the squash body from
the PR body read with that gate and **all** PR commit messages, not GitHub's
default squash body. The following JavaScript Eval route uses GraphQL cursor
pagination (the REST pull-request commit list is limited to 250 commits).
Run it in the PR repository with `owner`, `repo`, `number`, `gatedHead`,
and `gatedBody` set from the gated reads. Do not run it for by-hand landing.

```js
const query = `query($owner: String!, $repo: String!, $number: Int!, $endCursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      commits(first: 100, after: $endCursor) {
        totalCount
        pageInfo { hasNextPage endCursor }
        nodes { commit { oid message } }
      }
    }
  }
}`;
const pages = JSON.parse(await sh`gh api graphql --paginate --slurp -f query=${query} -f owner=${owner} -f repo=${repo} -F number=${number}`);
const connections = pages.map(p => p.data.repository.pullRequest.commits);
const nodes = connections.flatMap(c => c.nodes);
if (!nodes.length || connections.some(c => c.totalCount !== nodes.length) ||
    connections.at(-1).pageInfo.hasNextPage ||
    new Set(nodes.map(n => n.commit.oid)).size !== nodes.length ||
    nodes.at(-1).commit.oid !== gatedHead) {
  throw new Error("Incomplete or changed PR commit list; repeat the gate");
}
const result = await tool.daily_driver_commit_message({
  body: gatedBody,
  sourceMessages: nodes.map(n => n.commit.message),
});
const current = JSON.parse(await sh`gh pr view ${number} --json headRefOid,body`);
if (current.headRefOid !== gatedHead || current.body !== gatedBody) {
  throw new Error("PR changed; repeat the gate and prepare again");
}
const path = (await sh`mktemp`).trim();
try {
  await Bun.write(path, result.details.body);
  await sh`gh pr merge ${number} --squash --body-file ${path} --match-head-commit ${gatedHead}`;
} finally {
  await sh`rm -- ${path}`;
}
```

If a verified configured Omp co-author exists, supply it as `coAuthor` under
[`provenance`](../../provenance/references/omp.md#commits); never invent one.
Fail closed on unavailable pages, GraphQL errors, inconsistent counts, or a
changed head or body. Repeat the entire gate and preparation for a changed
head, never reuse a stale body. The conditional merge protects the remaining
head race; it leaves GitHub's PR-title-based squash subject unchanged. Keep
the merge authorization, CI and review gates; do not use the GitHub body-write
wrapper for this commit message.
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
agents route genuine attention-required handoffs to the orchestrator, not the
user. The `undertake` `Ready for review` report is different: the child returns
it to the orchestrator, which visibly relays it to the user's conversation.
Recoverable errors, CI waits, reminders, progress and ordinary final replies
do not notify. Notifications do not replace the record or chat handoff.


CI waiting uses `review-cycle`'s persistent named Bash service. Start the
service once, request `persist` through `write proc://<name>/mode`, and
confirm it with `read proc://<name>`. Do not pass `async` or `timeout` to
named-service mode. If persistence fails, stop the service and report the
failure; do not claim that CI remains watched.

This durability does not turn the process into an agent. A persistent service
can continue its bounded command after a client exits, but cannot reopen a
terminated owner. While the session is live, each implementor retains `pr`'s
owner continuation across renewable CI windows. An implementor result that says
only a detached service remains is unfinished, not an active agent watch.
Inspect its lifecycle and recover an ended owner on the same branch under
`Recovering an implementor`; do not wait for a user status request. Preserve
genuine prerequisites and avoid a second writer alongside a live owner.
After actual session shutdown, a later invocation must read the graph and
PR evidence; do not claim cross-shutdown recovery.

Register one `daily_driver_watch` backstop with action `register`, delaySeconds
`600`, and key `embark:<host>/<owner>/<repo>#<epic>` (host and repository
normalized to lowercase). Supply state with workflow `embark`, host, repository,
epic number, `nextAction`, `authorityRefs`, `holds`, `workers`, `services`,
and `observations`; include branch, worktree, ownerIssue and lastReported where
applicable. Record worker issue/job IDs, relevant PRs and exact compared
values, not policy dumps or credentials. Authority references are not approval;
holds persist until the user releases them.

Use `get` to recover the current record. After relevant current reads or
permitted work, `checkpoint` the latest snapshot and 600-second delay; an
unrelated question or event alone is not reconciliation. The module maintains
fallback coverage and coalesces due work with native worker/service turns.
Never create a second backstop or migrate delayed implementor reports into it.
For a live legacy backstop, cancel its exact known `triggerId` with
`daily_driver_cancel_schedule` before registering. If cancellation fails,
retain the legacy owner and report the failure; an unknown ID is not migrated.
Never cancel unrelated requested reminders.

On completion, by-hand or genuine human-only stop, call
`daily_driver_watch({action: "stop", key: <key>})`; stop the persistent named
CI service separately with `write proc://<name>/kill`. A stale wake does not
clear a hold or authorize registration. A stopped record stays stopped; only a
later explicitly authorized invocation may use the canonical key plus
`:run:<uuid>` for a fresh run. Timers stop on shutdown; same-session resume
restores journaled deadlines, but no process monitors across shutdown.



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

A repair authored by the orchestrator is reviewed by the shared advisor or
another independent reviewer, never by its author.


Recovering an implementor
=========================

Address corrections to the subagent identifier through agent messaging. Read
its lifecycle using `proc://<job-id>`, cancel through
`proc://<job-id>/kill`, and dispatch a replacement through `task` under
`Recover a session`.
