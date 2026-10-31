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
| `Implement` (issue-only research) | Record findings | `gh issue comment <number> --body-file <path>` |
| `Implement` (issue-only research) | Close completed research | `gh issue close <number> --reason completed` |

**Before `Claim the issue`, check the session title.** Read `sessionName` from `daily_driver_get_session`, which the claim already needs for its model and session id. Format the expected title as `#{number} {shortened issue title}` using `session-title`'s forty-character budget and shortening rules. If it differs, call `daily_driver_set_session_title({ title })` before `gh issue comment`; if it already matches, do not rename it. If the title surface is unavailable, report that limitation and continue without an alternate route, as `session-title` requires.

**`issue://<number>` carries the comments**, so the read in that row is one
call and returns the handoff content `SKILL.md` asks for. Where a cache miss
or a truncated resource leaves them out, `gh issue view <number> --json
comments` is the read that returns them — the same call the readiness report
makes further down this file.

`issue-deps` owns the edge writes, and has its own routes. So does
`issue-labels`, whose `references/omp.md` says why `--add-label` needs no
read-first and the Claude route does.

For a `task`, validate its `Model class` section and rationale through
[`issue-body`'s guidance](../../issue-body/references/model-classes.md) before
claim, repairing an old or invalid body where its handoff is otherwise
grounded. A frontier task also needs explicit approval and its exact work
envelope. A frontier `research` issue keeps that label and its narrow metadata
exception; do not impose the task template.

Use `daily_driver_get_session` to read the current model before branch creation
or claim when needed for the frontier restriction. If its effective route is
frontier and the issue is ordinary work, resolve a non-frontier agent using
[`embark`'s Omp class-routing rules](../../embark/references/omp.md#the-route-an-implementor-runs).
Hand off the full undertaking through `task`, or stop with the exact route gap;
the receiving session owns its branch and claim.

**Issue-only research writes use the issue client.** With no resume branch,
this route skips `task-worktree`; do not create or publish a branch. If a
resume branch exists, `task-worktree` attaches it, but the research route
leaves it unchanged. Post the complete answer with `gh issue comment
--body-file`, including `provenance`'s block; then close only when
`issue-body`'s research completion test holds. Failed or incomplete research
stays open.


The implementor
===============

Ordinary non-frontier implementation stays in the session running this
sequence. The frontier-only handoff exception runs before branch creation and
claim: resolve a supported non-frontier agent route using
[`embark`'s Omp class-routing rules](../../embark/references/omp.md#the-route-an-implementor-runs),
then use the `task` surface to dispatch a full `undertake #<issue>` to that
agent. The receiving session owns its worktree, claim, implementation, and
pull request. Do not dispatch if the route is unavailable or frontier; report
the exact configuration gap. A supported model switch may continue here only
after Omp reports a non-frontier execution identity.


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
| `The gate` | Post a missing completion notice | `review-cycle`'s notice route: `gh pr comment <number>` |
| `The gate` | Read the Blockers section | `gh pr view <number> --json body`, where `pr-body`'s Blockers section sits |
| `The milestone` | Read the draft state and report head | `gh pr view <number> --json isDraft,headRefOid` |
| `The milestone` | Read the existing comments | `gh pr view <number> --json comments` |
| `The milestone` | Post the report | `gh pr comment <number> --body-file <path>` |
| `Ready for review` | Take it out of draft | `gh pr ready <number>` |
| `Keep it current` | Merge the base branch in | `gh pr update-branch <number>` |
| `A round after ready goes back to draft` | Return it to draft | `gh pr ready <number> --undo` |

`Review the head`, `Fix, answer, resolve, push`, and `Verify the fix delta` are
`review-cycle`'s. Its `references/omp.md` names the reviewer task, durable
record, and bounded delta-pass contract.


The session
===========

**The claim's `provenance` block reads the model and the session id from
`daily_driver_get_session`**, the tool `extensions/daily-driver.js` registers.
`provenance`'s [`references/omp.md`](../../provenance/references/omp.md)
names the fields it answers and how the block records them.

For branch-free answer-only research, no task worktree exists and the claim
uses `Branch: none`. Otherwise the branch comes from the task worktree's Git
state: `git branch --show-current` runs in that worktree. On a resume that is
the adopted branch, which `Read the issue and its edges` took from the issue's
record; fetch it from the remote before `task-worktree` attaches it.
`OWNER/REPO` for the branch link comes from the remote `task-worktree`
resolved, never from an assumed `origin`.
Omp uses one branch identity for the local task and remote push branch. The
Claude primary-held designation exception does not apply to this route.

Task evidence state
-------------------

`daily_driver_task_state` stores private, active-branch task records. Call
`{action: "status"}` before another approval request or an unfinished stop.
For ordinary repository work not already active, call `begin`; do not activate
an ordinary question. Mutating calls take a JSON-string `record`.

- `begin`: `{taskId, operation, target, source: {sourceId, quote}}`. Use the
  latest external user source returned by `status`, not a copied handoff.
- `authorization`: `{id, kind: "user" | "workflow", operation, target,
  source: {sourceId, quote}, limits, conditions, expiresAt?, supersedes?,
  revokes?, freshConfirmation?}`. Sources must resolve to original user input
  or workflow instructions. Exact quotes establish provenance, not semantic
  permission. Read conditions against the original source before acting.
- `blocker`: `{operation, target, kind: "external" | "authorization" |
  "safety" | "execution", evidence: [{sourceId, quote}], authorizationIds: [],
  routes: [{route, disposition: "failed" | "prohibited" | "unavailable",
  evidence: {sourceId, quote}}], externalContribution,
  independentWork: {pending: [], completed: []}, resume}`.
- `complete`: `{summary}`. This records reported completion, not independent
  proof that acceptance criteria passed.

The tool never grants permission or replaces harness approval. Original
sources and tool evidence stay in session entries through compaction and
process resume. Cross-session handoffs carry source references and applicable
scope; copied agent text is not an original approval source in a new session.
Revalidate through the original source or existing workflow authorization.

The `session_stop` adapter checks active unfinished tasks and returns at most
two corrections for an unchanged observed condition. The count survives
resume; rewriting record labels does not renew it. Exhaustion emits an
execution-failure notice. It does not complete the task or invent an approval
requirement. User stop input and an aborted stop event prevent continuation.
The adapter does not prove arbitrary prose claims about approval or exhausted
routes. Preserve the original evidence and make no stronger claim.

Omp exposes an external-input origin on `input`, so scheduled reminders and
tool output do not become user authority. These semantics do not establish
equivalent hook provenance on another harness.


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
`session:` lines. Take its `createdAt`; where more than one comment carries
that shape, the earliest of them is the start — a later claim does not restart
the clock. A resumed session finds the start with the same read. An issue
with no recoverable claim leaves the timing `n/a`, per `SKILL.md`.

**Post the report before marking ready.** Read the existing comments with
`gh pr view <number> --json comments` and look for the fixed
`First-readiness report` marker. If none exists and the gate holds, write the
report as a pull-request comment:

    gh pr comment <number> --body-file <path>

Only after that write succeeds, run `gh pr ready <number>`. A failed report
write leaves the PR draft. A failed ready write preserves the report; on
retry, revalidate the current gate and do not duplicate or rewrite the
existing report.

**The provenance** is `provenance`'s block, read the way its
[`references/omp.md`](../../provenance/references/omp.md) names: the same
`daily_driver_get_session` call `The session` above uses.


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
Pending or unregistered checks use its persistent bounded watcher. Failed
checks return to `Fix, answer, resolve, push`; unavailable logs are a named
evidence blocker, not green. When CI on the current head is green and the
gate's notice read finds no completion notice, post the notice before
continuing the ready-gate work. A durable Omp service preserves its process,
but does not resume the owner: where no owner turn is running, report unfinished
work and the owner-resume requirement rather than claiming autonomous review.

The common merge loop remains mechanical. It does not assess the gate or
mark a draft ready.


The stop
========

`SKILL.md`'s `The stop` names each operation in words; these are the calls.

| Operation | Call |
| --------- | ---- |
| Read the issue's comments, for the claim and any equivalent handoff | `gh issue view <number> --json comments` |
| End the merge watch | `write proc://keep-current-<number>/kill`, the service name it was started under |
| Post the handoff | `gh issue comment <number> --body-file <path>` |

`--body-file` for the reason `Claim the issue`'s row gives. A CI watcher this
session holds is stopped by its `review-cycle` route. The pushed head is `git
ls-remote origin <branch>`.
