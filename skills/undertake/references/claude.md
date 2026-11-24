# Claude Code routes — undertake

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).


The issue
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the issue` | Search the open issues | `mcp__github__search_issues` |
| `Open the issue` | Open one, labelled; settle destination under [`issue`'s target repository rule](../../issue/SKILL.md#the-target-repository) and pass it here | `mcp__github__issue_write`, method `create`, with `labels`; set `owner` and `repo` when the target differs from the current repository |
| `Title the session` | Read the session's own id | `get_session` on the Claude Code Remote server, `session_id` omitted — `The session` below describes the call |
| `Title the session` | Set the title | `set_session_title`, with that id and `session-title`'s form |
| `Read the issue and its edges` | Read the body and the graph | `mcp__github__issue_read`, method `get` |
| `Read the issue and its edges` | Find the pull requests linked to the issue | `mcp__github__issue_read`, method `get` — `closed_by_pull_requests`, then `mcp__github__pull_request_read`, method `get`, for the head branch |
| `Read the issue and its edges` | Read the comments | `mcp__github__issue_read`, method `get_comments` |
| `Read the issue and its edges` | Label an issue that carries none | read `labels` with `mcp__github__issue_read`, then `mcp__github__issue_write`, method `update`, sending that set plus the new label |
| `Claim the issue` | Comment on the issue | `mcp__github__add_issue_comment` |
| `Implement` (issue-only research) | Record findings | `mcp__github__add_issue_comment` |
| `Implement` (issue-only research) | Close completed research | `mcp__github__issue_write`, method `update`, `state: closed`, `state_reason: completed` |

**The two title calls are `session-title`'s sequence, routed here so the step
is found without leaving this file.** The form, the budget and the shortening
stay in `session-title`; the server's prefix is whatever the session registers,
and `session-title`'s Claude reference says how absence is judged.

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

For a `task` or a classed `research` or `bug`, validate its `Model class`
section and rationale through
[`issue-body`'s guidance](../../issue-body/references/model-classes.md) before
claim, repairing an old or invalid body where its handoff is grounded. A
frontier `research` issue keeps that label and its narrow metadata exception;
do not impose the task template.

Before worktree or claim, attempt automatic class-appropriate selection once
through Claude Code's supported mechanism, preserving the invoking family and
provider where its mapping applies. Prefer a supported in-session route; a full
undertaking handoff is available under `The implementor` below.

The Claude Agent SDK's host-only `Query.setModel` is not an agent-callable
switch. Do not invent one or apply Omp role semantics here. If the class target,
credentials, controls or supported selection route are unavailable, briefly
name the class, attempted target, failure and retained actual route, then
continue ordinary work immediately. No confirmation, repair or replacement
dispatch is required. Explicit cancellation remains stopped.

**Issue-only research writes use the issue client.** With no resume branch,
this route skips `task-worktree`; do not create or publish a branch. If a
resume branch exists, `task-worktree` attaches it, but the research route
leaves it unchanged. Post the complete answer with
`mcp__github__add_issue_comment`, including `provenance`'s block; then close
with `mcp__github__issue_write` only when `issue-body`'s research completion
test holds. Failed or incomplete research stays open.

Retain applicable original authorization and its limits through delegation,
resume and compaction. Copied prose grants no approval. Never publish private
sources in issue or PR comments.


The implementor
===============

Prefer a supported in-session route. A full undertaking handoff through
`mcp__Claude_Code_Remote__create_session` or `Agent` is allowed when it supports
the required selection. The receiver owns the undertaking and the sender
stops; do not recursively hand off. If no supported selection route is
available, explain and continue with the invoking model rather than blocking.


The pull request
================

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the draft` | Open it | `pr`, which owns the call |
| `The gate` | Read the worktree and unpushed commits | `git status --porcelain` and `git log @{upstream}..HEAD --oneline`, through `Bash` in the task worktree; each prints nothing |
| `The gate` | Read acceptance evidence | Review the issue criteria against the diff, test results, runtime evidence, or other concrete observations |
| `The gate` | Read the branch against its base | `mcp__github__pull_request_read`, method `get` — `mergeable_state` |
| `The gate` | Read CI on the head | `mcp__github__pull_request_read`, **both** `get_check_runs` and `get_status` |
| `The gate` | Read the review threads | `mcp__github__pull_request_read`, `get_reviews`, `get_review_comments` and `get_comments` — `review-cycle`'s reference owns them |
| `The gate` | Read review evidence | Use `review-cycle`'s review and thread routes as needed; compare reviewed content with the current head |
| `The gate` | Read the Blockers section | `mcp__github__pull_request_read`, method `get` — `body`, where `pr-body`'s Blockers section sits |
| `Ready for review` | Take it out of draft | `mcp__github__update_pull_request`, `draft: false` |
| `Keep it current` | Invoke `pr`'s ongoing base maintenance | [`pr` route](../../pr/references/claude.md#keep-it-current) |
| `A round after ready goes back to draft` | Return it to draft | `mcp__github__update_pull_request`, `draft: true` |

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
more than one is a collision, not a pick. `task-worktree` may establish a
different local execution branch only when this is new work and schema-2
Worktrunk evidence confirms the designated branch is checked out in the
primary worktree. The claim links the designated remote push branch and names
the local execution branch separately. Otherwise the task-worktree branch
must agree with the designation, or with the adopted resume branch.

**A resume branch differing from the designation is not a collision.** The
adopted remote branch is the task's push/PR head. The user's standing decision
in [#719](https://github.com/jmcvetta/daily-driver/issues/719), reconfirmed in
[#817](https://github.com/jmcvetta/daily-driver/issues/817), is explicit
authorization: invoking `undertake` on an issue whose record names a resume
branch gives permission to push that branch and open or update its pull
request. A linked open PR, a `stand-down` handoff's `Branch:` line, or a
claim's branch link supplies the branch identity. The invocation supplies
consent; no permission sentence needs to be repeated in the prompt.

This authorization satisfies the Claude Code web instruction “NEVER push to a
different branch without explicit permission”, even when the recorded branch
differs from the designation. It does not cover an issue the user did not
invoke `undertake` on, an unrecorded branch, or a fork the session cannot push
to. More than one recorded branch remains a stop under `Read the issue and
its edges`.

Ask only when applicable authorization is absent or revoked, or an actual
instruction specifically requires fresh or narrower permission for this resume.
Do not infer that stricter requirement from unseen instructions. When a
question is needed, name both branches and the resume evidence in one line,
and wait for permission before pushing. Keep the adopted branch: never push
the work to the designated branch instead, and never open a second pull request
from it.

For repository work in the primary-held designation exception, use the
designated branch for the claim link, pushes, existing-PR lookup and PR
creation. Keep the execution branch local; `task-worktree`'s explicit
non-force refspec sets the designated remote branch as its upstream. CI reads
belong to the PR found on that remote head; never query or create CI state for
the local execution name.

`external_metadata.current_branches` is a different field and answers a
different question: what is checked out, not what the harness designated.

For branch-free answer-only research, no task worktree exists and the claim
uses `Branch: none`. Otherwise, where this call is absent, read the branch
from the task worktree's Git state, and its repository from the remote
`task-worktree` resolved. `provenance`'s reference says what the claim's block
records when the call itself is absent.



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

[`pr`'s `Keep it current` route](../../pr/references/claude.md#keep-it-current)
owns the common watch; this undertaking invokes it and does not start another.

Undertaking-specific continuation stays here. Use `review-cycle` for review
and fix-delta work, then apply `Ready for review`. A capped wait, review wall,
or human action reports unfinished work and its resume path; it never becomes
completion.

`review-cycle` borrows the cadence slot for its CI wait and hands it back as
`pr`'s reference directs. It does not own the standing watch.


The stop
========

`SKILL.md`'s `The stop` names each operation in words; these are the calls.

| Operation | Call |
| --------- | ---- |
| Read the issue's comments, for the claim and any equivalent handoff | `mcp__github__issue_read`, method `get_comments` |
| Cancel the common `Keep it current` wake | `pr`'s `Keep it current` route, `mcp__Claude_Code_Remote__delete_trigger` by its `trigger_id` |
| Drop a pull-request subscription | `mcp__github__unsubscribe_pr_activity`, one call per subscription |
| Post the handoff | `mcp__github__add_issue_comment` |

Read `git ls-remote origin <branch>` for the observed remote pushed head and
`git rev-parse HEAD` for the local tip. A failed read is unknown; preserve
local-only commits and their worktree path when a push fails.

`The wrap-up`'s `End the watch` uses the same two cancel routes before its
push. Neither is skipped because the orchestrator archives this session next:
a `send_later` trigger survives the session that armed it, and an archive
that fails leaves the subscription live.

