# Omp routes — review-cycle

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).


The review surface
==================

The **`reviewer`** task agent, dispatched through the `task` tool: a
code-review specialist, taking the review brief for the pull request and
reading the diff through `pr://`.

**It takes no effort level.** The round names the agent and nothing more, and
the depth judgement is the agent's. `SKILL.md`'s `Name the level` has nothing
to bind here — there is no remembered level to override.

**Its findings return locally and must be published as a GitHub review.** They
are not a transcript-only degradation. Give the reviewer the complete history,
reviewed SHA, and current head; the publication route below turns its findings
into the submitted threads that `Fix, answer, resolve, push` answers.


Fix-delta verification
======================

Dispatch exactly one `reviewer` task agent with a bounded brief. Give it the
pull request, base branch, full-review SHA, current SHA, original findings,
dispositions, and pass number. Require it to compare the pull request's
three-dot content at the reviewed SHA with its three-dot content at the current
SHA, exclude changes attributable only to the base branch, and inspect affected
callers. It reports only whether each implemented finding is solved and any
concrete regressions in that delta. It must not perform a full-PR audit or offer
style improvements.

The author records the result with `gh pr comment <number> --body-file <path>`:

```text
Review verification
scope reviewed: <sha>
pass: <n>
verified: <sha>
findings: <finding ids and dispositions>
outcome: <clear|defects|incomplete|unavailable>
defects: <none|concise list>
wall: <open|reached>
usage: unavailable
```

The task agent's result is independent evidence. The author writes this record
only after receiving it; it must not invent a verdict. Omp exposes no reviewer
token-usage value, so `usage: unavailable` is required.

Review-cycle completion notice
==============================

After a non-standalone round meets `SKILL.md`'s completion conditions and
`Does it go again?` starts no new full review, read the current head and
existing conversation comments with `gh pr view <number> --json headRefOid,comments`. If no existing comment
starts with `## Review cycle complete! 🎉` and names that head, write the
separate notice with `gh pr comment <number> --body-file <path>`. The body
starts with that heading, gives a short factual completion status, and names
the completed SHA. Re-read the head immediately before writing; a changed head
does not inherit the notice. A failed write is reported, never claimed.


The wait
========

**A bounded service observes CI; a live owner handles its result.** Use named
Bash services for `gh pr checks --watch` and, where needed, `gh run watch`.
Keep the owner continuation from [`pr`'s route](../../pr/references/omp.md#the-owner-continuation)
armed throughout the wait. A standalone review without a PR-maintenance watch
owns the same single reminder slot until its CI wait ends.

Capture the head SHA, a unique window identifier, and a UTC deadline fifteen
minutes ahead. Start a service without `async` or the Bash `timeout` parameter,
which service mode rejects:

```text
{
  "command": "printf 'ci-watch-started sha=<sha> window=<window> deadline=<utc>\\n'; exec timeout --signal=TERM --kill-after=5s <remaining>s gh pr checks --watch <pr> --repo <owner>/<repo>",
  "name": "ci-<pr>-<short-sha>-<window>",
  "cwd": "<task-worktree>",
  "ready": {"log": "ci-watch-started"}
}
```

The launch marker proves launch only, not registration or green CI. GNU
`timeout` bounds this observation window, sends TERM at its deadline, then KILL
after five seconds. Use strictly positive remaining seconds, never zero
(which disables the limit). Exit 124 means window expiration, not CI failure.
Other nonzero exits also prove no green verdict. Diagnose missing utilities
or an unavailable watch route rather than starting an unbounded shell job.

Before starting, inspect the recorded service with `read proc://<name>`.
Reuse a running watcher; starting a live name restarts it and resets its
bound. Inspect immediately after launch. If it has exited, read CI rather
than requesting persistence. Otherwise write `persist` to `proc://<name>/mode`
and read back `persist=true`. On mode failure or missing confirmation, stop
the running service and diagnose the failure. Do not call it durable or use
`detached` for a bounded CI watch.

Use `wait` with no arguments only when no other work remains. Caller-owned
service results also auto-deliver. A reminder, a service result, and `wait`'s
own safety-cap return are wakes, not verdicts. Inspect the existing service
and reread CI; do not launch a duplicate because a reminder fired.

The verdict
-----------

Read the head before each launch and after every watch, then read all three
sources for that exact SHA, every page:

| Source | Call |
| ------ | ---- |
| Check runs | `gh api --paginate --slurp /repos/{owner}/{repo}/commits/{sha}/check-runs` |
| Commit statuses | `gh api --paginate --slurp /repos/{owner}/{repo}/commits/{sha}/status` |
| Workflow runs | `gh api --paginate --slurp '/repos/{owner}/{repo}/actions/runs?head_sha={sha}&per_page=100'` |

`gh pr checks --watch` observes the rollup only. It can exit before workflow
jobs register. Its exit, even zero, never replaces these reads.

Do not filter workflow inventory by status. Keep a run only if `head_sha`
matches and `pull_requests` is empty or contains this PR. A branch name does
not establish identity. Count the current `run_attempt` only. A run is terminal
only when `status` is `completed` and `conclusion` is non-null. Queued,
requested, waiting, pending, in-progress, null, and unknown states remain
nonterminal. Terminal failure returns to `Fix, answer, resolve, push`; it is
not a reason to keep waiting for green.

A nonterminal workflow after the rollup watcher exits gets a run service
within the same window:

```text
{
  "command": "printf 'run-watch-started sha=<sha> window=<window> deadline=<utc> run=<run-id> attempt=<n>\\n'; exec timeout --signal=TERM --kill-after=5s <remaining>s gh run watch <run-id> --repo <owner>/<repo>",
  "name": "ci-<pr>-<short-sha>-<window>-run-<run-id>-<attempt>",
  "cwd": "<task-worktree>",
  "ready": {"log": "run-watch-started"}
}
```

Apply the same inspection, persistence, and cleanup rules. No `--fail-fast`,
unmanaged shell job, or shell `sleep`. Fine-grained tokens cannot use
`gh run watch`; diagnose that route limit and use the managed owner reminder
for fresh inventory reads where authorized reads still work. A watch without
`--exit-status` can return zero for a failed run; read the verdict.

Renew the window, retain ownership
----------------------------------

The deadline is absolute **within a window**, not forever for that head.
Record it in the service marker and reuse its remainder across all watches
in that window, including after a resume. At expiration:

1. Read the head, service status, and all three CI sources.
2. If current-head work remains nonterminal, end any old window services,
   record a new window identifier and fifteen-minute deadline, and continue
   with a new bounded watch. Do this without another user prompt. Keep the
   existing owner reminder; do not duplicate it or report a human blocker.
3. If the head moved, stop old-head services and discard their verdict.
   Reobserve the new head before starting its window.
4. If inventory is terminal and no known registration gap remains, continue
   the review or failure diagnosis. Stop obsolete CI services. A standalone
   wait cancels its reminder; an ongoing PR owner retains its common slot.

A missing window record is not permission to reset a live watcher. Inspect
the process, preserve its bound, and recover its log where possible. After
the old service ends, fresh head and inventory reads can establish a new
window. Never infer green or abandon ownership because the record is missing.

Zero check runs, no statuses, and no matching workflow mean unregistered,
not green. A successful subset with a known missing check is incomplete too.
Do not repeatedly relaunch an empty rollup watcher. Keep the managed reminder
and reobserve registration on its next wake. Diagnose persistent registration
gaps from repository configuration and workflow evidence; elapsed time alone
is not proof of a blocker. A denied, malformed, truncated, or failed read
requires diagnosis and leaves the verdict unknown, never a passing empty
inventory. Report a genuine missing capability or external prerequisite with
its evidence and resume path; do not label a timeout as one.

Process durability is not session resumption
--------------------------------------------

The common owner reminder is separate from the persistent CI service and
detached currency service. It sends an Omp follow-up turn to a live idle
session. Retain it during CI waits; on a wake, inspect before renewing any
service. Its prompt names the PR, branch, window/service identities, next
unfinished action, and user-stop guard. Once CI is terminal, a stale CI wake
reads current state and continues the current phase, not a new old-head wait.

`daily_driver_schedule` timers are cleared on `session_shutdown`. A service
can outlive that shutdown but cannot launch or resume an agent. Do not claim
cross-shutdown recovery. A live idle or parked owner is not shutdown: retain
its reminder instead of returning only an owner-resume requirement. If the
reminder call fails, diagnose and keep supervising through service completion
while possible; report the exact continuation gap, not a fictitious watch.

On an owner turn, inspect the maintenance service and take `pr`'s currency
checkpoint before assessing readiness. Current-head CI in flight defers base
updates; a completed old-head run is not current evidence. Resolve mechanical
conflicts and service failures under the existing undertaking rules; ask only
for a genuine semantic decision or missing external prerequisite. Merge,
close, and user stop cancel both reminder and owned services. A stale wake
after a user stop performs no work.



Review history, publication, and threads
========================================

Before dispatch, read every submitted review with `gh api --paginate /repos/{owner}/{repo}/pulls/{n}/reviews`. Read the complete thread graph with a
paginated GraphQL `PullRequest.reviewThreads` query, including `id`,
`isResolved`, `isOutdated`, review/comment IDs, replies, SHAs, paths, lines,
and bodies. A REST comments page alone is not complete history and does not
contain the `PRRT_…` ID needed to resolve a thread.

After the reviewer returns, re-read the head and its diff anchors. Compare the
returned findings with the review history and recorded review identifier before
posting; a resumed run must not duplicate a review already submitted for that
SHA. Put line-specific findings in `review.json` and create one submitted
review:

```json
{
  "event": "COMMENT",
  "commit_id": "<reviewed-sha>",
  "body": "<clean or cross-cutting review summary>",
  "comments": [
    {
      "path": "<path>",
      "side": "RIGHT",
      "line": 42,
      "body": "<finding, with a suggestion block when useful>"
    }
  ]
}
```

Run `gh api --method POST /repos/{owner}/{repo}/pulls/{n}/reviews --input
review.json`. Use `start_side` and `start_line` for a valid range. A clean or
unanchorable review has no `comments` entry and uses the submitted summary.
Never invent an anchor. On changed head, invalid anchor, absent `gh`, or GitHub
failure, retain the findings and report publication as incomplete.

| Operation | Call |
| --------- | ---- |
| Read reviews | `gh api --paginate /repos/{owner}/{repo}/pulls/{n}/reviews` |
| Read threads | paginated `gh api graphql` query of `PullRequest.reviewThreads` |
| Publish review | `gh api --method POST /repos/{owner}/{repo}/pulls/{n}/reviews --input review.json` |
| Reply on a thread | `gh api -X POST /repos/{owner}/{repo}/pulls/{n}/comments/{comment_id}/replies` |
| Resolve a thread | `gh api graphql` with the `resolveReviewThread` mutation |

The identifier trap `SKILL.md` states applies to the last two: the mutation
takes the thread's `PRRT_…` node ID, while reply takes the comment's numeric
ID. The review REST endpoint returns a review ID; record it with the reviewed
SHA and dispositions so later rounds have a stable duplicate check.
