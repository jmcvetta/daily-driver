# Claude Code routes — undertake

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).


The issue
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the issue` | Search the open issues | `mcp__github__search_issues` |
| `Open the issue` | Open one, labelled | `mcp__github__issue_write`, method `create`, with `labels` |
| `Read the issue and its edges` | Read the body and the graph | `mcp__github__issue_read`, method `get` |
| `Read the issue and its edges` | Find the pull requests linked to the issue | `mcp__github__issue_read`, method `get` — `closed_by_pull_requests`, then `mcp__github__pull_request_read`, method `get`, for the head branch |
| `Read the issue and its edges` | Read the comments | `mcp__github__issue_read`, method `get_comments` |
| `Read the issue and its edges` | Label an issue that carries none | read `labels` with `mcp__github__issue_read`, then `mcp__github__issue_write`, method `update`, sending that set plus the new label |
| `Claim the issue` | Comment on the issue | `mcp__github__add_issue_comment` |

**The comments are a second call on this client.** `mcp__github__issue_read`
takes a `method`, and `get` returns the body, the labels and the hierarchy
flags — not the comments. `get_comments` is what returns them, so a session
that makes only the `get` call reads none of the handoff content `SKILL.md`
asks for, and cannot tell whether the issue is claimed either.

**The read in the labelling row is not optional.** `labels` replaces the whole set, so
an update sending one label deletes every other label the issue had — the
stock and bot-owned ones `issue-labels` says to leave alone included. An
issue carrying none of the standard's six is not an issue carrying none.

`issue-deps` owns the edge writes, and has its own routes. So does
`issue-labels`, whose `references/claude.md` states that trap where the label
write lives.

For a `task`, read the `Model class` section, validated and repaired through
[`issue-body`'s guidance](../../issue-body/references/model-classes.md) where
its body is old or invalid, before the claim. That guidance is dispatch's —
`embark` selects a route against it before assigning work — and nothing here
compares the class to this session's own capability.


The implementor
===============

No route, and that is the rule rather than a gap. `SKILL.md`'s `Implement`
owns it: the session running the sequence writes the code itself, so nothing
here dispatches `mcp__Claude_Code_Remote__create_session` or the `Agent` tool
for the body of the work. Both routes exist on this harness and both belong to
`embark`, which uses them to run several task issues at once — the web session
is its primary route here. The one dispatch inside this sequence is
`review-cycle`'s briefed subagent at `Verify the fix delta`, named in that
skill's own reference file.


The pull request
================

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the draft` | Open it | `pr`, which owns the call |
| `The gate` | Read the branch against its base | `mcp__github__pull_request_read`, method `get` — `mergeable_state` |
| `The gate` | Read CI on the head | `mcp__github__pull_request_read`, **both** `get_check_runs` and `get_status` |
| `The gate` | Read the review threads | `mcp__github__pull_request_read`, `get_reviews`, `get_review_comments` and `get_comments` — `review-cycle`'s reference owns them |
| `The gate` | Read the review record | `mcp__github__pull_request_read`, method `get_comments` — the round's own `Review` and `Review verification` comments |
| `The gate` | Read the completion notice | `mcp__github__pull_request_read`, method `get_comments`, to the last page — the latest `## Review cycle complete! 🎉` comment by the claim's author |
| `The gate` | Post a missing completion notice | `review-cycle`'s notice route: `mcp__github__add_issue_comment` |
| `The gate` | Read the Blockers section | `mcp__github__pull_request_read`, method `get` — `body`, where `pr-body`'s Blockers section sits |
| `Ready for review` | Take it out of draft | `mcp__github__update_pull_request`, `draft: false` |
| `Keep it current` | Merge the base branch in | `mcp__github__update_pull_request_branch` |
| `A round after ready goes back to draft` | Return it to draft | `mcp__github__update_pull_request`, `draft: true` |
| `The milestone` | Read the readiness state | `mcp__github__pull_request_read`, method `get` — `draft`, `mergeable_state`, `head.sha` |
| `The milestone` | Read the existing comments | `mcp__github__pull_request_read`, method `get_comments` |
| `The milestone` | Post the report | `mcp__github__add_issue_comment` |

`Review the head`, `Fix, answer, resolve, push`, and `Verify the fix delta` are
`review-cycle`'s. Its `references/claude.md` names the full-review surface and
the briefed-subagent route `Verify the fix delta` runs on; a pass that dispatch
genuinely fails is what keeps the pull request draft.

**The gate's CI read is two calls, not one.** `mergeable_state` reports a
draft's own status ahead of its checks — `draft`, or `blocked` where the
repository requires a review — so a session reading CI out of that field
reads nothing about CI. `get_check_runs` and `get_status` are the union
`review-cycle`'s wait defines, and `SKILL.md`'s `The gate` uses the same one.


The session
===========

`mcp__Claude_Code_Remote__get_session`, with `session_id` omitted, describes
the caller. `task-worktree` consumes the designated branch when the call
supplies exactly one for this repository; `provenance`'s
[`references/claude.md`](../../provenance/references/claude.md) names the
same call's model and session fields for `Claim the issue`'s block.

| What | Field |
| ---- | ----- |
| The designated branch | `session_context.outcomes[].git_repository.git_info.branches` |
| The repository it is pushed to | `session_context.outcomes[].git_repository.git_info.repo` |

Both branch fields are arrays. Read the outcome whose `git_info.repo` names the
repository this work will be pushed to. Exactly one branch is a designation;
more than one is a collision, not a pick. The branch checked out in the task
worktree must agree before the claim is posted — the designated branch, or the
adopted resume branch where `Read the issue and its edges` found one.

**A resume branch differing from the designated one is not a collision.** The
adopted branch is the task branch. The session's own instructions may still
require explicit permission to push to a branch other than the designated one.
Where they do, ask the user once, in one line naming both branches and the
resume evidence (the pull request, handoff comment or claim that named it),
then push to the adopted branch. Never push the work to the designated branch
instead, and never open a second pull request from it.

`external_metadata.current_branches` is a different field and answers a
different question: what is checked out, not what the harness designated.

Where this call is absent, read the branch from the task worktree's Git
state, and its repository from the remote `task-worktree` resolved.
`provenance`'s reference says what the claim's block records when the call
itself is absent.


The milestone
=============

`SKILL.md` owns what the report says and when it is owed; these are the calls
that read the readiness state, find the claim's timestamp, and post it.

**The readiness state is `mcp__github__pull_request_read`, method `get`** —
the same call `The gate` makes, asking a different question. Three fields
answer `SKILL.md`'s: `draft`, which must be false; `mergeable_state`; and
`head.sha`, the SHA the report binds to.

**Here `clean` is the only yes**, and that is the difference from the gate.
The gate runs while the pull request is still a draft, where this field
reports `draft` or `blocked` and says nothing about the merge; the milestone
runs after the draft is cleared, where the same field finally answers the
mergeability question the report attests to. So `unstable` is a check that is
no longer green, `behind` a base the branch does not carry, `dirty` a
conflict, `blocked` a required review outstanding, and `unknown` GitHub
saying it cannot determine the answer yet — the indeterminate readiness
`SKILL.md` rules out. Each of them is a wait, not a milestone.

This call returns no `mergeable` boolean — measured on the server this
session holds, 2026-09-18 — so `mergeable_state` is the whole answer rather
than half of it.

**The start is the claim comment's `created_at`.** Read the issue's comments
with `mcp__github__issue_read`, method `get_comments` — the read `Read the
issue and its edges` already makes — find the claim by its branch link and
`Model:` and `session:` lines, and take `created_at`; where more than one
comment carries that shape, the earliest of them is the start — a later
claim does not restart the clock. The resumed sequence
makes this read anyway at `Read the issue and its edges`; an issue with no
recoverable claim leaves the timing `n/a`, per `SKILL.md`.

**The report posts with `mcp__github__add_issue_comment`** — a pull request's
comments are issue comments, so the claim's write is the report's. The same
call only writes, so read first: `mcp__github__pull_request_read`, method
`get_comments`, on the pull request, the report found by its opening line, `First-readiness
report`, the marker `SKILL.md` fixes, and a resumed sequence that finds it
posts nothing.

**The provenance** is `provenance`'s block, read the way its
[`references/claude.md`](../../provenance/references/claude.md) names: the
same `mcp__Claude_Code_Remote__get_session` call `The session` above uses.


The orchestrator
================

`SKILL.md`'s `Reporting to an orchestrator` applies where the system prompt
names an orchestrator session id — `embark`'s dispatch puts it there. The
report is a one-shot Routine bound to that session:

| Field of `mcp__Claude_Code_Remote__create_trigger` | Value |
| ---- | ----- |
| `persistent_session_id` | The orchestrator's session id |
| `run_once_at` | The next whole UTC minute plus one, RFC3339 |
| `prompt` | The report, opening with its fixed line |
| `name` | The report's fixed opening line |
| `initiation` | `own_followup` |

The tool is deferred: load it with `ToolSearch`, `select:` its name, before the
first report. The Routine disables itself once it fires, so there is nothing
to delete.

**Not `fire_trigger`, and not `send_later`.** A manual `fire_trigger` on a
Routine bound to the orchestrator returns success and delivers nothing.
`send_later` fires into the calling session only, so it reaches the
implementor, not the orchestrator.
[`0028`](../../../docs/notes/0028-the-report-is-a-scheduled-routine.md) has
the measurements.

**This Routine is not the cadence's slot.** It is bound to another session,
so `The cadence` below neither reuses it nor counts it.


The cadence
===========

`Open the draft` starts the one durable cadence on this harness:
`mcp__Claude_Code_Remote__send_later`, two minutes out, cancelled with
`mcp__Claude_Code_Remote__delete_trigger`. It survives the session that armed
it, which is what makes continuation across turns possible at all. Reaching
ready retains this cadence; it does not arm a second one.

**Each wake carries its own instructions.** The prompt handed to `send_later`
states the whole check-in, self-contained, in this order:

1. **Re-arm first.** `mcp__Claude_Code_Remote__send_later`, two minutes out,
   with the same prompt. A pending trigger is reused; a wake that ends with no
   trigger in flight has lost the undertaking's continuation.
2. **Read state, currency, and the merge floor.** Read `state`, `draft`,
   `mergeable_state`, `head.sha`, `get_check_runs`, and `get_status`. A merged
   or closed pull request deletes the re-armed trigger and exits. If either CI
   endpoint reports a run in flight, skip the merge. Otherwise `behind`,
   `draft`, `blocked`, or an indeterminate merge state runs
   `mcp__github__update_pull_request_branch`, whose own reply settles
   currency; `dirty` is the conflict stop.
3. **Assess the resulting head.** After a currency test that can move the
   head, read both CI endpoints again; without one, the floor read is the
   assessment. A changed head invalidates earlier CI and readiness evidence.
   Pending or unregistered checks use `review-cycle`'s bounded wait; failed
   checks return to `Fix, answer, resolve, push`, and missing logs remain an
   evidence blocker. When CI on the current head is green and the gate's
   notice read finds no completion notice, post the notice before continuing
   the ready-gate work. Continue the remaining review or ready-gate work when
   CI permits it. A capped wait, review wall, or human action reports unfinished
   work and its resume path; it never becomes completion.

The slot it occupies is the same slot `review-cycle`'s wait borrows and hands
back. That ownership starts before ready, including red results and capped
waits. A pending cadence wake is reused unless a CI wait borrowed it; on
`End the wait`, cancel that borrowed wake and arm exactly one replacement.
