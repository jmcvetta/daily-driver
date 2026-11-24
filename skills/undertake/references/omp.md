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
| `Open the issue` | Open one, labelled; settle destination under [`issue`'s target repository rule](../../issue/SKILL.md#the-target-repository) and pass it here | `gh issue create --label task [--repo OWNER/REPO when target differs from current repository]` |
| `Read the issue and its edges` | Read the body, the graph and the comments | `issue://<number>`, comments included |
| `Read the issue and its edges` | Label an issue that carries none | `gh issue edit <number> --add-label task` |
| `Claim the issue` | Comment on the issue | `daily_driver_gh_write({ args: ["issue", "comment", <number>, "--body-file", <path>] })` |
| `Implement` (issue-only research) | Record findings | `daily_driver_gh_write({ args: ["issue", "comment", <number>, "--body-file", <path>] })` |
| `Implement` (issue-only research) | Close completed research | `gh issue close <number> --reason completed` |

Before claim, read `sessionName` with `daily_driver_get_session`; use
[`session-title`](../../session-title/references/omp.md) for the title call.

**`issue://<number>` carries the comments**, so the read in that row is one
call and returns the handoff content `SKILL.md` asks for. Where a cache miss
or a truncated resource leaves them out, `gh issue view <number> --json
comments` is the read that returns them.

`issue-deps` owns the edge writes, and has its own routes. So does
`issue-labels`, whose `references/omp.md` says why `--add-label` needs no
read-first and the Claude route does.

Validate readiness and model class through `issue-body` before routing.

Before worktree creation or claim, call `daily_driver_route_undertaking` with
`{ issue: <positive issue number>, modelClass: "mechanical" | "routine" |
"intermediate" | "complex" | "frontier" }`.
Validate readiness first. Call the routing tool alone in its assistant tool
batch. Do not batch discovery, worktree creation, claim, or other tool calls with
it. The tool selects within the invoking family and provider without rewriting
shared roles.

Read `details.undertaking` from the result or `daily_driver_get_session`:
`issue`, `modelClass`, `selectedModel`, `observedModel`, `status`, and
`capability`, with optional `reason` and `warning`. The session result also
reports provider and non-secret authentication route. `status` is `selected`
after initial route selection; malformed or cancelled state can report
`blocked`. A selected route is not proof of the observed execution identity or
class suitability. Keep the requested class, selected model, and observed model
separate. Do not claim verification from a selector or status alone.



After the pull request is ready, or answer-only research is completed and
recorded, call `daily_driver_finish_undertaking({ issue: <positive issue number> })`
for the completed undertaking before reusing the session for another issue.
Do not finish a stopped or incomplete undertaking. Selecting a different issue
returns an error and preserves the existing owner and route. Finish the
completed undertaking or resume the existing one before selecting another.
A finish call with the wrong issue also returns an error and preserves the
existing state.

The successful finish persists and releases the undertaking before its
automatic completion notification. Do not call `daily_driver_notify` again for
that completion. A stopped or incomplete undertaking is not a completion.

For a genuine unresolved human handoff, before the chat handoff call
`daily_driver_notify({ reason: "attention_required", key: "<stable action key>",
message: "<specific action needed>" })`. The key identifies the required
action, not an attempt; use a different key for a different action. Keep the
key nonblank and at most 160 characters, the message nonblank and at most 400,
and both free of control characters. Do not put secrets in either. The
notification does not replace the chat handoff or durable record. A child
reports to its orchestrator instead; recoverable errors, CI waits, reminders,
progress and ordinary final replies do not notify.


**Operator recovery does not require a model turn.** Run `/undertaking status`
locally to inspect the owner, selected model and effort, host selection, last
observed execution identity, authentication route category, and last rejection.
The command remains available after provider rejection or malformed saved state.
Run `/undertaking cancel <issue>` with the exact owner reported by status to
cancel unfinished routing. When status reports `cancelOwner: invalid`, use
`/undertaking cancel invalid` for that malformed current-session record.
Cancellation aborts and waits for local work, releases only the owned lease,
retires pending handoffs, and revokes owned children. It persists cancellation
without completing the issue. It preserves transcript, worktree, and branch.
A later undertaking requires a fresh initial selection. Repeated cancellation
with no owner is a no-op. Use the workflow's stop handoff separately when work
must be stood down.


**Issue-only research writes use the issue client.** With no resume branch,
this route skips `task-worktree`; do not create or publish a branch. If a
resume branch exists, `task-worktree` attaches it, but the research route
leaves it unchanged. Post the complete answer with
`daily_driver_gh_write({ args: ["issue", "comment", <number>, "--body-file",
<path>] })`; the wrapper adds provenance. Then close only when
`issue-body`'s research completion test holds. Failed or incomplete research
stays open.


The implementor
===============

Prefer the in-session route. A full `undertake #<issue>` handoff through `task`
is permitted. The receiving session owns the worktree, claim, implementation,
and pull request. The sender stops rather than repeating the handoff or
supervising duplicate work.

Explicit top-level frontier selection and native `^provider/model`
consultations are ordinary model choices. They do not change the undertaking's
recorded class or initial selection. Retry-fallback and prewalk transitions are
automatic.


The pull request
================

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the draft` | Open it | `pr`, which owns the call |
| `The gate` | Read the worktree and unpushed commits | `git status --porcelain` and `git log @{upstream}..HEAD --oneline`, through `bash` in the task worktree; each prints nothing |
| `The gate` | Read acceptance evidence | Review the issue criteria against the diff, test results, runtime evidence, or other concrete observations |
| `The gate` | Read the branch against its base | `gh pr view <number> --json mergeStateStatus` |
| `The gate` | Read CI on the head | `gh pr view <number> --json statusCheckRollup` |
| `The gate` | Read the review threads | `review-cycle`'s `references/omp.md` owns them |
| `The gate` | Read review evidence | Use `review-cycle`'s review and thread routes as needed; compare reviewed content with the current head |
| `The gate` | Read the Blockers section | `gh pr view <number> --json body`, where `pr-body`'s Blockers section sits |
| `Ready for review` | Take it out of draft | `gh pr ready <number>` |
| `Ready for review` | Deliver the user-facing report | A dedicated final conversation message after observing `gh pr ready <number>` succeed; include the fixed report opening and task/PR/moment fields |
| `Ready for review` | Copy to an addressed orchestrator | Omp has no remote session-messaging client: include the report in the child result returned to its orchestrator. The orchestrator must visibly relay it in the user-facing conversation; parent-only receipt does not satisfy user delivery |
| `Ready for review` | Report delivery failure | State the failed delivery once in the available conversation; leave the PR ready and continue |
| `Keep it current` | Merge the base branch in | `gh pr update-branch <number>` |
| `A round after ready goes back to draft` | Return it to draft | `gh pr ready <number> --undo` |

`Review the head`, `Fix, answer, resolve, push`, and `Verify the fix delta` are
`review-cycle`'s. Its `references/omp.md` names the reviewer task, durable
record, and bounded delta-pass contract.


The session
===========

**Body-bearing GitHub writes use `daily_driver_gh_write`**, which appends the
provenance block from the live execution context and caches the installed Omp
version once per extension instance. Do not read model/session identity, run
`omp --version`, or format a block for these writes. `daily_driver_get_session`
remains available for separate tasks such as reading the session name for
title handling. `provenance`'s [`references/omp.md`](../../provenance/references/omp.md)
defines the block and edit-deduplication behavior.

For branch-free answer-only research, no task worktree exists and the claim
uses `Branch: none`. Otherwise the branch comes from the task worktree's Git
state: `git branch --show-current` runs in that worktree. On a resume that is
the adopted branch, which `Read the issue and its edges` took from the issue's
record; fetch it from the remote before `task-worktree` attaches it.
`OWNER/REPO` for the branch link comes from the remote `task-worktree`
resolved, never from an assumed `origin`.
Omp uses one branch identity for the local task and remote push branch. The
Claude primary-held designation exception does not apply to this route.

Retain applicable original authorization and its limits through delegation,
resume and compaction. Copied prose grants no approval. Never publish private
sources in issue or PR comments.




Common PR maintenance
=====================

Use [`pr`'s Omp route](../../pr/references/omp.md) for the currency checkpoint,
detached watch, catch-up look, and cancellation. `Open the draft` starts or
reuses that watch, including while CI or review is pending. `Ready for review`
does not start another one.

The undertaking catch-up look
-----------------------------

Answer direct user questions from known evidence before tools; where state is
unknown, say which read is needed. An explicit stop follows `The stop`.
Otherwise take the common catch-up look, then continue this sequence:
**Currency is not completion.** After a currency test that can move the head,
read `gh pr view <number> --json statusCheckRollup` for the resulting
`headRefOid`; `review-cycle`'s three-source read remains the CI verdict.
Pending or unregistered checks retain its renewable bounded observation and
the common PR owner reminder. Window expiration is not a task blocker.
Failed checks return to `Fix, answer, resolve, push`; unavailable logs require
diagnosis, not a green verdict. A live idle owner must retain the common reminder. Process
persistence alone does not resume an owner after session shutdown.

The common merge loop remains mechanical. It does not assess the gate or
mark a draft ready.


The stop
========

`SKILL.md`'s `The stop` names each operation in words; these are the calls.

| Operation | Call |
| --------- | ---- |
| Read the issue's comments, for the claim and any equivalent handoff | `gh issue view <number> --json comments` |
| Cancel the owner reminder | `daily_driver_cancel_schedule({triggerId})`, using the common PR slot |
| End the merge watch | `write proc://keep-current-<number>/kill`, the service name it was started under |
| Post the handoff | `daily_driver_gh_write({ args: ["issue", "comment", <number>, "--body-file", <path>] })` |

The wrapper appends provenance to the handoff body. Do not format or include a
block in the body file. A CI watcher this session holds is stopped by its
`review-cycle` route. Read `git ls-remote origin <branch>` for the remote head
and `git rev-parse HEAD` for the local tip. Mark failed reads unknown and
record local-only commits with their worktree path.
