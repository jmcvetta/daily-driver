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

**Before `Claim the issue`, check the session title.** Read `sessionName` from
`daily_driver_get_session` for title handling only. Format the expected title
as `#{number} {shortened issue title}` using `session-title`'s forty-character
budget and shortening rules. If it differs, call
`daily_driver_set_session_title({ title })` before the wrapper call; if it
already matches, do not rename it. The wrapper reads live model and session
identity for attribution. If the title surface is unavailable, report that
limitation and continue without an alternate route, as `session-title` requires.

**`issue://<number>` carries the comments**, so the read in that row is one
call and returns the handoff content `SKILL.md` asks for. Where a cache miss
or a truncated resource leaves them out, `gh issue view <number> --json
comments` is the read that returns them — the same call the readiness report
makes further down this file.

`issue-deps` owns the edge writes, and has its own routes. So does
`issue-labels`, whose `references/omp.md` says why `--add-label` needs no
read-first and the Claude route does.

For a `task` or a classed `research` or `bug`, validate its `Model class`
section and rationale through
[`issue-body`'s guidance](../../issue-body/references/model-classes.md) before
claim, repairing an old or invalid body where its handoff is otherwise
grounded. A frontier task also needs explicit approval and its exact work
envelope. A frontier `research` issue keeps that label and its narrow metadata
exception; do not impose the task template.

Before worktree creation or claim, call `daily_driver_route_undertaking` with
`{ issue: <positive issue number>, modelClass: "mechanical" | "implementation" |
"integration" | "reasoning" | "frontier", frontierApproval?: <recorded approval
and envelope> }`.
Validate readiness and frontier approval first; the approval argument is evidence,
not authorization by itself. Call the routing tool alone in its assistant tool
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


Admission snapshots the effective candidate identities and effort for the
initial undertaking route. Visible incompatible retry and prewalk candidates
fail before dispatch. This admission does not impose a continuing request-route
guard. Agent-initiated worker selection and fallback remain subject to the
class, frontier approval, and route-integrity requirements as workflow policy;
operator model, provider, and effort changes remain permitted and must not be
blocked or reversed.

If the known family is absent from the class table, a prominent warning names
the family, class, and retained provider/model. Continue immediately on the
invoking model, provider, and effort without confirmation. Class suitability
remains unverified. Preserve this disposition for agent-initiated worker
dispatch. If a child cannot retain the initial route, work in the invoking
session. A missing or cleared class, unavailable initial target, or incompatible
agent assignment is a configuration gap; unknown identity and later operator
selection are not absent-family continuation or route violations.

Independently configured `reviewer`, `scout`, `security-reviewer`, and `seance`
helpers are not issue implementation workers for class selection. This does not
define their cancellation ownership.

After the pull request is ready, or answer-only research is completed and
recorded, call `daily_driver_finish_undertaking({ issue: <positive issue number> })`
for the completed undertaking before reusing the session for another issue.
Do not finish a stopped or incomplete undertaking. Selecting a different issue
returns an error and preserves the existing owner and route. Finish the
completed undertaking or resume the existing one before selecting another.
A finish call with the wrong issue also returns an error and preserves the
existing state.

**Operator choices remain in control after admission.** Request rejection or
resume does not restore or require the initially selected model or effort.
Operators may change model, provider, and effort at any later point; routing
must not block those changes. The initial selection remains the undertaking's
assigned worker identity for agent-initiated dispatch and fallback checks.
Native consultations and independent helper routes remain separate.

**Operator recovery does not require a model turn.** Run `/undertaking status`
locally to inspect the owner, selected model and effort, host selection, last
observed execution identity, authentication route category, and last rejection.
The command remains available after provider rejection or malformed saved state.
Run `/undertaking cancel <issue>` with the exact owner reported by status to
cancel unfinished routing. When status reports `cancelOwner: invalid`, use
`/undertaking cancel invalid` for that malformed current-session record.
Cancellation aborts and waits for local work, releases only the owned lease,
retires pending handoffs, and revokes owned children. It persists cancellation
without completing the issue. It preserves transcript, worktree,
branch, and approval evidence. A later undertaking requires fresh normal
admission. Repeated cancellation with no owner is a no-op. Use the workflow's
stop handoff separately when work must be stood down.


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
is permitted only if the effective child route and every visible fallback can
be constrained to the same family, provider, backend, authentication route,
and exact class. The receiving session verifies its own execution and owns the
worktree, claim, implementation, and pull request. The sender stops rather
than repeating the handoff or supervising duplicate work. If the surface cannot
establish those constraints, stop and report the precise gap.

After manual escalation of an existing task, first repair the plan under this
skill's *Manual frontier escalation* policy. Use the route above only when
its constraints are established; transfer the existing work and authority,
not a new claim. Otherwise deliver the plan and report the missing return route.

The adapter admits explicit top-level frontier selection and native
`^provider/model` consultations without changing the undertaking worker.
Consultation responses do not verify a pending worker. Its tools remain
available for diagnosis, plan repair, and reporting; this is not a frontier
implementation exception. Native mention dispatch pins the branch-authorized
model and constrains the child's actual requests, including after resume.
Retry-fallback and prewalk markers do not establish operator authorization.
The adapter guards its routing tool and observed dispatch, not arbitrary
trusted extensions that call Omp's top-level model setter.


The pull request
================

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the draft` | Open it | `pr`, which owns the call |
| `The gate` | Read the worktree and unpushed commits | `git status --porcelain` and `git log @{upstream}..HEAD --oneline`, through `bash` in the task worktree; each prints nothing |
| `The gate` | Read the diff against the acceptance section | `gh pr diff <number> --name-only` |
| `The gate` | Read the branch against its base | `gh pr view <number> --json mergeStateStatus` |
| `The gate` | Read CI on the head | `gh pr view <number> --json statusCheckRollup` |
| `The gate` | Read the review threads | `review-cycle`'s `references/omp.md` owns them |
| `The gate` | Read the review record | `gh pr view <number> --json comments` — the round's own `Review` and `Review verification` comments |
| `The gate` | Read the completion notice | `gh pr view <number> --json comments`, to the last page — the latest `## Review cycle complete! 🎉` comment by the claim's author |
| `The gate` | Post a missing completion notice | `review-cycle`'s notice route: `daily_driver_gh_write({ args: ["pr", "comment", <number>, "--body-file", <path>] })` |
| `The gate` | Read the Blockers section | `gh pr view <number> --json body`, where `pr-body`'s Blockers section sits |
| `The milestone` | Read the draft state and report head | `gh pr view <number> --json isDraft,headRefOid` |
| `The milestone` | Read the existing comments | `gh pr view <number> --json comments` |
| `The milestone` | Post the report | `daily_driver_gh_write({ args: ["pr", "comment", <number>, "--body-file", <path>] })` |
| `Ready for review` | Take it out of draft | `gh pr ready <number>` |
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


The milestone
=============

`SKILL.md` owns what the report says and when it is owed; these are the calls
that read the readiness state, find the claim's timestamp, and post it.

**The report is posted while the pull request is still a draft.** Read the
state and head with:

    gh pr view <number> --json isDraft,headRefOid

`isDraft` must be true, and `headRefOid` is the SHA the report binds to. The
gate already establishes branch currency, current-head CI, review completion,
resolved threads, the completion notice and absence of human blockers.
`mergeable` and `mergeStateStatus` are not readiness prerequisites here:
draft states can mask the underlying result, and a post-ready `CLEAN` read
would put the report after the transition it must precede.

**The start is the claim comment's `createdAt`.** `issue://<issue>` carries
the comments, so `Read the issue and its edges` already has them; `gh issue
view <issue> --json comments` is the same read where that resource is not to
hand. The claim is the comment carrying the branch link and the `Model:` and
`Session:` lines; a historical block with a lowercase `session:` field is the
same claim, not a different one. Take its `createdAt`; where more than one
comment carries that shape, the earliest of them is the start — a later claim
does not restart the clock. A resumed session finds the start with the same
read. An issue with no recoverable claim leaves the timing `n/a`, per
`SKILL.md`.

**Post the report before marking ready.** Read the existing comments with
`gh pr view <number> --json comments` and look for the fixed
`First-readiness report` marker. If none exists and the gate holds, write the
report as a pull-request comment with
`daily_driver_gh_write({ args: ["pr", "comment", <number>, "--body-file",
<path>] })`.

Only after that write succeeds, run `gh pr ready <number>`. A failed report
write leaves the PR draft. A failed ready write preserves the report; on
retry, revalidate the current gate and do not duplicate or rewrite the
existing report.

The wrapper attaches the report's provenance automatically. The report body
must not include a new attribution block or identity lookup.


Common PR maintenance
=====================

Use [`pr`'s Omp route](../../pr/references/omp.md) for the currency checkpoint,
detached watch, catch-up look, and cancellation. `Open the draft` starts or
reuses that watch, including while CI or review is pending. `Ready for review`
does not start another one.

The undertaking catch-up look
-----------------------------

Take the common catch-up look first, then continue this sequence:

**Currency is not completion.** After a currency test that can move the head,
read `gh pr view <number> --json statusCheckRollup` for the resulting
`headRefOid`; `review-cycle`'s three-source read remains the CI verdict.
Pending or unregistered checks retain its renewable bounded observation and
the common PR owner reminder. Window expiration is not a task blocker.
Failed checks return to `Fix, answer, resolve, push`; unavailable logs require
diagnosis, not a green verdict. When CI on the current head is green and the
gate's notice read finds no completion notice, post it before continuing the
ready gate. A live idle owner must retain the common reminder. Process
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
`review-cycle` route. The pushed head is `git ls-remote origin <branch>`.
