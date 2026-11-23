# Omp routes — review-cycle

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).


The review surface
==================

Native [Open Code Review](https://github.com/alibaba/open-code-review) (`ocr`
CLI) is the review surface for both `Review the head` and eligible `Verify the
fix delta` passes. Never dispatch or fall back to Omp's `reviewer` task agent,
and do not add a helper process, second provider framework, custom OCR rules, or
second publication path. Omp continues to own CI waits, review history, GitHub
publication, finding dispositions, and readiness records.

Installation
-------------

Before either analysis stage, check whether `ocr` is on `PATH`. Reuse an
existing installation without upgrading it. If missing, require Bun and install
the published package in the user's global Bun installation:

```sh
bun add --global @alibaba-group/open-code-review
```

Ensure Bun's global executable directory is on `PATH`, then verify
`ocr --version` before running a review. If Bun is absent, installation fails,
or `ocr` remains unavailable, report the precise failure and the review as
`unavailable`; do not silently switch package managers or reviewers.

Installation does not configure a provider or supply credentials. Preserve
existing OCR configuration and complete the provider setup below separately.

Model and effort configuration
------------------------------

OCR and its provider setup are local prerequisites; credentials stay outside Git
and GitHub issues. Persistent model and review-round effort live in
`~/.opencodereview/config.json`:

```sh
ocr config set model <vercel-model-slug>
ocr config set effort low
```

The initial local configuration uses Vercel AI Gateway (configured once as an
OpenAI-compatible provider with its base URL as documented by OCR) with the
operator's current Mistral model and OCR `effort low` (one review round per
subtask). `ocr config unset effort` restores OCR's default `medium`, or the
operator may save `medium` or `high` later.

**Daily Driver invokes `ocr review` without `--model` or `--effort`.** OCR
resolves both from its own persistent configuration on every full review and
fix-delta pass, so changing either saved setting changes the next review without
editing this skill. Operator manual runs may still pass `--model` or `--effort`,
but this route does not set them. `SKILL.md`'s `Name the level` does not apply
here: do not infer `medium` or `high` from the diff, and do not infer separate
model reasoning parameters.

Keep the rest of OCR's native pipeline at its stock defaults: rule resolution,
file grouping, positioning, reflection, filtering, concurrency, timeouts,
retries, and token budgets. The only integration-only invocation differences are
immutable `--from` and `--to` commits, `--audience agent --format json`,
owner-only `--background-file` and `--output` files, and no `--analysis`
(because the review cycle consumes findings rather than OCR's separate
behavior-analysis report).

Full-review invocation and acceptance
-------------------------------------

Compute `<merge-base-sha>` from the pull request's base ref and
`<reviewed-head-sha>`, then run native OCR from the task worktree:

```sh
ocr review --repo <task-worktree> --from <merge-base-sha> --to <reviewed-head-sha> \
  --audience agent --format json \
  --background-file <owner-only-context-file> --output <owner-only-result-file>
```

Store `<owner-only-context-file>` and `<owner-only-result-file>` outside the
checkout and build artifacts with owner-only permissions (`0600`). The context
file contains the complete submitted-review and thread history, dispositions,
reviewed SHA, current head, and applicable requirement context. OCR rejects
sanitized background content over 8,000 characters: on that error, report the
full review `unavailable`; do not truncate, retry with less history, or fall
back to the `reviewer` task agent.

Accept a full-review result only when all of the following hold:

- JSON parsing succeeds.
- `manifest.terminal_state` is `complete`.
- `manifest.input.resolved_base` equals `<merge-base-sha>` and
  `manifest.input.resolved_head` equals `<reviewed-head-sha>`.
- `manifest.coverage.failed` is empty.

A usable JSON result that fails any of those checks is `incomplete`; a CLI or
authentication failure, background-size rejection, or missing or unparseable
JSON is `unavailable`. Never submit an `incomplete` or `unavailable` result as a
completed full review. Report its findings and coverage gap locally and name
publication incomplete; it cannot satisfy readiness.

Full-review publication and reviewer identity
---------------------------------------------

OCR findings return locally and must be published as one submitted `COMMENT`
review through `daily_driver_gh_write` (see `Review history, publication, and
threads` below) with `commit_id` equal to `<reviewed-head-sha>`. They are not a
transcript-only degradation.

The submitted review summary names the OCR session (`OCR session:
<session_id>`), the OCR version and requested model when reported, complete
coverage, and files reviewed. Including `OCR session: <session_id>` lets a
resumed run compare that identifier and `<reviewed-head-sha>` against review
history and avoid duplicate publication.

Map each OCR comment as follows:

- Positive equal `start_line` and `end_line`: `path`, `side: "RIGHT"`, and
  `line` equal to that line.
- Positive increasing lines (`0 < start_line < end_line`): `path`,
  `start_side: "RIGHT"`, `start_line`, `side: "RIGHT"`, and `line` equal to
  `end_line`.
- Both lines zero, reversed lines, or an anchor absent from the pull request
  diff: put the finding in the submitted summary; never invent an anchor.
- Inline body: severity, category, and `content`; append `suggestion_code` as a
  GitHub suggestion block only when present and useful. Never publish
  `thinking`.

Re-read the head and revalidate every anchor immediately before publication.
Preserve existing repeat-finding reconciliation, replies, resolution, and
provenance. A clean result has no `comments` entry and uses the submitted
summary.

Pass `reviewerSession` from OCR's `session_id` (omit only when absent),
`reviewerModel: "unreported"`, and no `reviewerProvider` to
`daily_driver_gh_write`. OCR's configured `llm.model`, `llm.provider`, and
manifest execution identity are requested identity, not proof of the
backend-served identity. Keep each review and verification pass paired with its
own OCR session. The normal Omp publisher block remains automatic.


Fix-delta verification
======================

First apply `SKILL.md`'s content classification (`Verify the fix delta`): pure
formatting and unchanged pull-request content need no pass. Never dispatch or
substitute the `reviewer` task agent.

For a behavioral delta, let `<scope>` be the full-review SHA and `<current>` be
the current SHA. Native OCR may run only when both preconditions hold:

- `git merge-base <scope> <current>` equals `<scope>` (excludes rewritten
  ancestry).
- `git merge-base <base-ref> <scope>` equals `git merge-base <base-ref>
  <current>` (excludes a delta mixed with newer base-branch content, which OCR's
  commit-range review cannot separate).

If either precondition fails, record `outcome: unavailable` with the precise
precondition failure in `defects:`; do not run a full-PR audit or substitute the
`reviewer` task agent.

When eligible, run the same stock JSON command from the task worktree without
`--model`, `--effort`, or `--analysis`:

```sh
ocr review --repo <task-worktree> --from <scope> --to <current> \
  --audience agent --format json \
  --background-file <owner-only-context-file> --output <owner-only-result-file>
```

OCR's saved model and effort apply unchanged. Store the context and output files
outside the checkout and artifacts with owner-only permissions (`0600`). The
context file contains the original findings, dispositions, base branch,
`<scope>`, `<current>`, pass number, and this bounded instruction: report only
unsolved implemented findings and concrete regressions in the delta, inspect
affected callers, and do not restart a full-PR audit or offer style work. If OCR
rejects sanitized background content over 8,000 characters, record
`outcome: unavailable`; do not truncate, retry with less history, or fall back.

Require the same manifest validation: JSON parsing succeeds,
`manifest.terminal_state` is `complete`, `manifest.input.resolved_base` equals
`<scope>`, `manifest.input.resolved_head` equals `<current>`, and
`manifest.coverage.failed` is empty.

The author records the pass with `daily_driver_gh_write({ args: ["pr",
"comment", <number>, "--body-file", <path>], reviewerModel: "unreported",
reviewerSession: <ocr session_id> })` (omitting `reviewerProvider`, and omitting
`reviewerSession` when absent):

```text
Review verification
scope reviewed: <sha>
pass: <n>
verified: <sha>
findings: <finding ids and dispositions>
outcome: <clear|defects|incomplete|unavailable>
defects: <none|concise list>
wall: <open|reached>
usage: <summary.total_tokens (with input/output counts when present)|unavailable>
```

Map OCR's result to `outcome` and `defects` as follows:

| Condition | `outcome` | `defects` |
| --- | --- | --- |
| Complete exact delta and zero OCR comments | `clear` | `none` |
| Complete exact delta and one or more OCR comments | `defects` | Concise OCR findings |
| Usable OCR JSON with missing/mismatched identity or incomplete coverage | `incomplete` | Known defects, otherwise the coverage gap |
| Failed precondition, CLI/authentication failure, or missing/unparseable JSON | `unavailable` | Precise failure, or `unavailable` |

`scope reviewed`, `verified`, `pass`, and `findings` retain their existing
meanings; `findings` lists the original IDs and dispositions. Compute `wall`
under the existing consecutive-defective-pass rule, not from OCR prose. Set
`usage` from `summary.total_tokens`, with input/output counts when present, or
`unavailable` when absent. Pass reviewer identity to `daily_driver_gh_write`
exactly as for the full review (`reviewerModel: "unreported"`, `reviewerSession`
from OCR's `session_id` when present, and no `reviewerProvider`).

OCR's result is independent evidence. The author records OCR's result only after
receiving it and must not replace it with its own verdict. Ineligible,
incomplete, unavailable, or defective results do not approve the head. The
wrapper adds provenance; do not add a block to the record.

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

Before running OCR, read every submitted review with `gh api --paginate /repos/{owner}/{repo}/pulls/{n}/reviews`. Read the complete thread graph with a
paginated GraphQL `PullRequest.reviewThreads` query, including `id`,
`isResolved`, `isOutdated`, review/comment IDs, replies, SHAs, paths, lines,
and bodies. A REST comments page alone is not complete history and does not
contain the `PRRT_…` ID needed to resolve a thread.

After OCR returns an accepted full-review result, re-read the head and
revalidate every diff anchor. Compare the OCR session (`OCR session:
<session_id>`) and reviewed SHA against the review history before posting; a
resumed run must not duplicate a review already submitted for that OCR session
and SHA. Put mapped inline findings in `review.json` and create one submitted
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

Run `daily_driver_gh_write({ args: ["api", "--method", "POST",
"/repos/{owner}/{repo}/pulls/{n}/reviews", "--input", "review.json"],
reviewerModel: "unreported", reviewerSession: <ocr session_id> })` (omitting
`reviewerProvider`, and omitting `reviewerSession` when absent). The wrapper
labels the reviewer and publisher on the summary and every inline comment in the
JSON body. Use `start_side` and `start_line` for a valid increasing line range.
A clean or unanchorable review has no `comments` entry and uses the submitted
summary. Never invent an anchor. On changed head, invalid anchor, absent `gh`,
or GitHub failure, retain the findings and report publication as incomplete.

| Operation | Call |
| --------- | ---- |
| Read reviews | `gh api --paginate /repos/{owner}/{repo}/pulls/{n}/reviews` |
| Read threads | paginated `gh api graphql` query of `PullRequest.reviewThreads` |
| Publish review | `daily_driver_gh_write({ args: ["api", "--method", "POST", "/repos/{owner}/{repo}/pulls/{n}/reviews", "--input", "review.json"], reviewerModel: "unreported", reviewerSession: <ocr session_id> })` |
| Reply on a thread | `daily_driver_gh_write({ args: ["api", "-X", "POST", "/repos/{owner}/{repo}/pulls/{n}/comments/{comment_id}/replies", "--input", "reply.json"] })` |
| Resolve a thread | `gh api graphql` with the `resolveReviewThread` mutation |

The identifier trap `SKILL.md` states applies to the last two: the mutation
takes the thread's `PRRT_…` node ID, while reply takes the comment's numeric
ID. The review REST endpoint returns a review ID; record it with the reviewed
SHA and dispositions so later rounds have a stable duplicate check. The wrapper
adds and deduplicates provenance for review and reply bodies; do not add a new
block to `review.json` or `reply.json`.
