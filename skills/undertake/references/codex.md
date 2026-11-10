# Codex routes — undertake

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in
[`claude.md`](claude.md), Oh My Pi's in [`omp.md`](omp.md).

**Codex has no GitHub tool of its own** — no `mcp__github__*` server, and no
built-in `github` tool with an `issue://` or `pr://` cache behind it. There is
one client, `gh` in the shell.


The issue
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the issue` | Search the open issues | `gh search issues` |
| `Open the issue` | Open one, labelled | `gh issue create --label task` |
| `Read the issue and its edges` | Read the body, the graph and the comments | `gh issue view <number> --json body,labels,comments,blockedBy,subIssues,parent` |
| `Read the issue and its edges` | Label an issue that carries none | `gh issue edit <number> --add-label task` |
| `Claim the issue` | Comment on the issue | `gh issue comment <number> --body-file <path>` |
| `Implement` (issue-only research) | Record findings | `gh issue comment <number> --body-file <path>` |
| `Implement` (issue-only research) | Close completed research | `gh issue close <number> --reason completed` |

`--body-file` rather than `-b`: the claim carries backticks and markdown
links, and a double-quoted shell argument substitutes the backticks before
`gh` sees them. `pr-body`'s [`codex.md`](../../pr-body/references/codex.md)
makes the same argument at length.

`comments` is in that field list because `SKILL.md` reads the comments as
content: a correction to the body, a constraint an earlier session found, a
decision taken in the thread. It serves `Claim the issue` as well — a claim
already on the issue is what says the sequence is being re-entered, or that
another session got there first — but that is the smaller of the two reasons.
A read without the field has neither.

The `--json` fields in the read row need `gh` at its stated floor.
`issue-deps` owns the edge reads and picks its own client — two clients here
rather than three — so read that skill's routes before believing an empty
answer. So does `issue-labels`, whose `references/codex.md` says why
`--add-label` needs no read-first and the Claude route does.

For a `task` or a classed `research` or `bug`, validate its `Model class`
section and rationale through
[`issue-body`'s guidance](../../issue-body/references/model-classes.md) before
claim, repairing an old or invalid body where its handoff is grounded. A
frontier assignment also needs explicit approval and its exact envelope. A
frontier `research` issue keeps that label and its narrow metadata exception;
do not impose the task template.

Before worktree creation or claim, resolve classed work within the invoking
family and provider. Preserve backend, authentication route, and fallbacks where
the surface supports them; never deliberately substitute a provider. If the
known family is absent from the class table, prominently warn with the family,
class, and retained provider/model, then continue immediately on the invoking
model and effort without confirmation. Identity does not establish class
suitability. Frontier approval and actual route constraints still apply.

For a mapped family, a missing or cleared class, unavailable target, or
incompatible assignment is a gap. Unknown family or identity is not an absent
family. This surface exposes no measured agent-callable in-session model switch;
do not invent one. Report unsupported controls and do not claim verification.

**Issue-only research writes use the issue client.** With no resume branch,
this route skips `task-worktree`; do not create or publish a branch. If a
resume branch exists, `task-worktree` attaches it, but the research route
leaves it unchanged. Post the complete answer with `gh issue comment
--body-file`, including `provenance`'s block; then close only when
`issue-body`'s research completion test holds. Failed or incomplete research
stays open.

Authorization and unfinished stops
----------------------------------

The installed task-state hooks supply a command bound to the native session
and actor. Run that exact command with `{action, record}` JSON on stdin.
`record` may be a JSON object or a JSON string on this CLI route. Read `isError`
in the JSON answer: a controller rejection exits 0. Run the call on its own, so
its exact output matches the receipt it records and stays out of task evidence.
Do not select another session identity. The [shared contract operations](../../../docs/harness-integration.md#task-state-operations)
define every action and record, including authorization, blocker and reported
complete.

Codex-specific packaging loads common hooks and `hooks/task-state-codex.json`.
Only the latter registers `Interrupt`; Claude never reads that event.
Trust the installed definitions through `/hooks`. The measured CLI 0.160.0
emits no `UserPromptSubmit` for its Stop-generated continuation. Native child
input carries `agent_id` and remains interpretation, not root user authority.
Do not infer authority from unstable transcript fields.

Private ledgers under `CODEX_HOME` (default `~/.codex`) retain contracts,
sources, revocation/expiry conditions and correction counts through process
resume. `SessionStart(source: compact)` restores the contract after compaction.
`Interrupt` records cancellation without granting another turn. A resume does
not renew an exhausted correction allowance. This adds no durable wake.
The [runtime integration](../../../docs/harness-integration.md#hook-harness-boundary)
records prerequisites and the bounded native-event proof.


The implementor
===============

For a mapped family, prefer a verified in-session route. A full undertaking
handoff through `multi_agent_v1` is allowed only if it can constrain and verify
the exact class and same family, provider, backend, authentication
route, and fallbacks. Its model selection is unmeasured; do not assume that
constraint exists. The receiving session owns the undertaking and the sender
stops without recursively handing off. When neither route can be established,
report the exact gap. For an absent family, retain the invoking session if a
child cannot retain its route; do not spawn a replacement merely to obtain a
mapping.

After manual escalation of an existing task, first repair the plan under this
skill's *Manual frontier escalation* policy. Use the route above only when
its constraints are established; transfer the existing work and authority,
not a new claim. Otherwise deliver the plan and report the missing return route.


The pull request
================

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the draft` | Open it | `pr`, which owns the call |
| `The gate` | Read the worktree and unpushed commits | `git status --porcelain` and `git log @{upstream}..HEAD --oneline`, through the shell in the task worktree; each prints nothing |
| `The gate` | Read the diff against the acceptance section | `gh pr diff <number> --name-only` |
| `The gate` | Read the branch against its base | `gh pr view <number> --json mergeStateStatus` |
| `The gate` | Read CI on the head | `gh pr view <number> --json statusCheckRollup` |
| `The gate` | Read the review threads | `review-cycle`'s `references/codex.md` owns them |
| `The gate` | Read the review record | `gh pr view <number> --json comments` — the round's own `Review` and `Review verification` comments |
| `The gate` | Read the completion notice | `gh pr view <number> --json comments`, to the last page — the latest `## Review cycle complete! 🎉` comment by the claim's author |
| `The gate` | Post a missing completion notice | `review-cycle`'s notice route: `gh pr comment <number>` |
| `The gate` | Read the Blockers section | `gh pr view <number> --json body`, where `pr-body`'s Blockers section sits |
| `The milestone` | Read the draft state and report head | `gh pr view <number> --json isDraft,headRefOid` |
| `The milestone` | Read the existing comments | `gh pr view <number> --json comments` |
| `The milestone` | Post the report | `gh pr comment <number> --body-file <path>` |
| `Ready for review` | Take it out of draft | `gh pr ready <number>` |
| `Keep it current` | Invoke `pr`'s ongoing base maintenance | [`pr` route](../../pr/references/codex.md#keep-it-current) |
| `A round after ready goes back to draft` | Return it to draft | `gh pr ready <number> --undo` |

`Review the head`, `Fix, answer, resolve, push`, and `Verify the fix delta` are
`review-cycle`'s. Its `references/codex.md` names the full-review surface and
the briefed-subagent route `Verify the fix delta` runs on; a pass that dispatch
genuinely fails is what keeps the pull request draft.


The session
===========

**Codex exposes no session id, so the claim's `provenance` block records
`session: n/a`** — the marker `SKILL.md` prescribes, not a diagnostic about
the missing surface. `provenance`'s
[`references/codex.md`](../../provenance/references/codex.md) names how the
`Model:` line is read.

For branch-free answer-only research, no task worktree exists and the claim
uses `Branch: none`. Otherwise the branch comes from the task worktree's Git
state: `git branch --show-current` runs in that worktree. On a resume that is
the adopted branch, which `Read the issue and its edges` took from the issue's
record (`gh issue view <number> --json closedByPullRequestsReferences,comments`);
fetch it from the remote before `task-worktree` attaches it. `OWNER/REPO` for
the branch link comes from the remote `task-worktree` resolved, never from an
assumed `origin`.

Codex uses one branch identity for the local task and remote push branch. The
Claude primary-held designation exception does not apply to this route.


The milestone
=============

`SKILL.md` owns what the report says and when it is owed; these are the calls
that read the readiness state, find the claim's timestamp, and post it. They
are `gh` throughout, as everywhere on this harness.

**The report is posted while the pull request is still a draft.** Read the
state and head with:

    gh pr view <number> --json isDraft,headRefOid

`isDraft` must be true, and `headRefOid` is the SHA the report binds to. The
gate already establishes branch currency, current-head CI, review completion,
resolved threads, the completion notice and absence of human blockers.
`mergeable` and `mergeStateStatus` are not readiness prerequisites here:
draft states can mask the underlying result, and a post-ready `CLEAN` read
would put the report after the transition it must precede.

**The start is the claim comment's `createdAt`.** `gh issue view <issue>
--json comments` is the read `Read the issue and its edges` already makes —
`comments` is in its field list — and the claim carries the branch link and
the `Model:` and `session:` lines. Take its `createdAt`; where more than one
comment carries that shape, the earliest is the start. A resumed session
finds it with the same read. An issue with no recoverable claim leaves the
timing `n/a`, per `SKILL.md`.

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
[`references/codex.md`](../../provenance/references/codex.md) names: it
follows `The session` above.


The cadence
===========

[`pr`'s `Keep it current` route](../../pr/references/codex.md#keep-it-current)
owns the common watch and its no-durable-wake limit. This undertaking invokes
that maintenance; it does not claim or start a timer or autonomous review.

Undertaking-specific continuation stays here. When current-head CI is green,
post a missing review completion notice before continuing the ready-gate work.
Use `review-cycle` for review and fix-delta work, then apply `Ready for review`
and `The milestone` below. State unfinished work and the owner-resume
requirement; never call a clean branch, an up-to-date response, or a draft
completion.


The stop
========

`SKILL.md`'s `The stop` names each operation in words; these are the calls.
The Codex route has no durable actor to cancel; `pr`'s reference owns the
stop semantics. Say that no timer or subscription exists only when the
handoff leaves unfinished work.

| Operation | Call |
| --------- | ---- |
| Read the issue's comments, for the claim and any equivalent handoff | `gh issue view <number> --json comments` |
| Post the handoff | `gh issue comment <number> --body-file <path>` |

The pushed head is `git ls-remote origin <branch>`.

