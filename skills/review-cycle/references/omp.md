# Omp routes — review-cycle

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).


The review surface
==================

The **`reviewer`** task agent, dispatched through the `task` tool, is the
default review surface: a code-review specialist taking the pull request brief
and reading the diff through `pr://`. An explicit operator selection overrides
this default for its stated scope under `Operator-selected review method`.

**It takes no effort level.** The round names the agent and nothing more, and
the depth judgement is the agent's. `SKILL.md`'s `Name the level` has nothing
to bind here — there is no remembered level to override.

**Record returned findings durably on the pull request.** Give the reviewer
the relevant history, reviewed revision, and current head. The routes below
support submitted reviews and ordinary pull-request comments; neither one
publication shape nor a matching author account is a prerequisite. Existing
credible independent human or agent review can supply this evidence without
another task dispatch.

Use ordinary `provenance` for published artifacts. Do not inspect persisted
reviewer transcripts to reconstruct model, provider, or session identity.
Identify the independent review by its available result or link; the wrapper's
normal provenance describes the writer and is not proof of review coverage.

Operator-selected review method
-------------------------------

Honor the operator's selected independent method for its stated scope, including
a switch from a running review. Stop the superseded invocation before starting
its replacement. Do not silently fall back, install a replacement framework, or
change persistent reviewer configuration. The default method's prerequisites
are not prerequisites for a different selected method.

Give an invoked reviewer the pull request, actual base branch, reviewed and
current revisions, relevant history and dispositions, and applicable issue or
specification requirements. For a full review, require the
complete three-dot pull-request diff, affected callers, and relevant tests to
be inspected for concrete correctness defects and unmet requirements, not style.
For a fix-delta pass, use the bounded brief in `Fix-delta verification` below.
The reviewer must not edit files or run project checks; the author owns CI.
Apply `SKILL.md`'s effort rule only when the selected surface takes a level.

Require a result tied to the reviewed content, with coverage limits and
concrete findings. Include valid diff anchors where available. A failed
invocation or partial coverage is not a clean result. Do not silently switch
methods again on failure.

Keep the selected method and scope clear in the review evidence. Use native
publication or the routes below, and link an existing published result instead
of duplicating it. Record fix-delta results concisely as described below;
no execution-identity fields or reviewer-session inspection are required.


Fix-delta verification
======================

When a new pass is needed, dispatch one `reviewer` task agent unless the
operator selected another independent method. Existing credible independent
human or agent review of the delta can also satisfy the pass.

Give the reviewer the pull request, base branch, prior reviewed revision,
current revision, relevant original findings and dispositions. Require it to
compare the relevant pull-request content at those revisions, excluding
base-only changes, and inspect affected callers. Comparing the three-dot
pull-request diffs is one way to establish the content delta; do not infer it
from commit ancestry alone. It reports whether each implemented finding is
solved and any concrete regressions in that delta. It must not perform a
full-PR audit or offer style improvements.

After receiving the independent result, link it or record a concise account
of the checked content and fixes, outcome, and any defects or coverage limits:

```text
daily_driver_gh_write({ args: ["pr", "comment", <number>, "--body-file", <path>] })
```

No fixed verification heading, field set, empty values, usage data, or pass
counter is needed. Preserve enough result history to recognize repeated
unresolved defects and failed approaches. The author must not invent the
reviewer's verdict. The wrapper adds ordinary provenance; do not add a new
block to the body.

The wait
========

For a PR transferred to the [opt-in active supervisor](../../pr/references/omp.md#opt-in-active-supervision),
that actor owns the single durable observation/delivery route. Do not start the
legacy CI service or owner fallback below alongside it. Handle a supervisor
delivery, acknowledge only through its fresh-read work tool, use that result's
`observed` evidence as the work input without a prerequisite GitHub inventory,
and retain the same three-source current-head verdict and independent-review
requirements.
These transport operations do not establish readiness.

**A bounded service observes CI; a live owner handles its result.** Use named
Bash services for `gh pr checks --watch` and, where needed, `gh run watch`.
Keep the owner continuation from [`pr`'s route](../../pr/references/omp.md#the-owner-continuation)
throughout the wait. A review inside a PR owner's watch uses its `pr:` key and
`pr` state, never a second record. A standalone review registers one
`review-cycle:<host>/<owner>/<repo>#<pr>` key with workflow `review-cycle`
and initial delaySeconds 120. Normalize host and repository case; supply the
same structured fields and authority/hold safeguards as the PR route.
Store exact compared observations including head, CI window and deadline, the
service names and next unmet action. Use `get` to recover state and checkpoint
only after current reads or permitted work. Retain 120 seconds while current-head
CI is pending or unregistered; otherwise apply the PR route's backoff.
If replacing a legacy owner, first cancel its exact known trigger ID; on
failure retain it and report the failure without registering a second owner.
Unknown IDs are not silently migrated; unrelated reminders are untouched.

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
service results also auto-deliver. A continuation, a service result, and `wait`'s
own safety-cap return are wakes, not verdicts. Inspect the existing service
and reread CI; do not launch a duplicate because a continuation fired.

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
`gh run watch`; diagnose that route limit and use the managed owner continuation
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
   existing owner continuation; do not duplicate it or report a human blocker.
3. If the head moved, stop old-head services and discard their verdict.
   Reobserve the new head before starting its window.
4. If inventory is terminal and no known registration gap remains, continue
   failure diagnosis or the readiness gate. Review need not wait for this.
   Stop obsolete CI services. A standalone wait stops its matching watch; an
   ongoing PR owner retains its common record.

A missing window record is not permission to reset a live watcher. Inspect
the process, preserve its bound, and recover its log where possible. After
the old service ends, fresh head and inventory reads can establish a new
window. Never infer green or abandon ownership because the record is missing.

Zero check runs, no statuses, and no matching workflow runs are initially
unknown, not green. A successful subset with a known missing check is
incomplete too. Do not repeatedly relaunch an empty rollup watcher. Keep the
managed continuation and reobserve registration on its next wake while an
applicable check may still register.

For an empty inventory, establish absence using complete current evidence:

- Read the PR's base and head SHA, event and changed paths, including all
  pages. Read the repository's workflow inventory and the workflow definitions
  applicable to that event and revision; evaluate branch, path and other
  trigger filters. Include external check providers and any other configured
  sources, not only GitHub Actions.
- Read the base branch's applicable protection and rulesets, including inherited
  rules, and their required check contexts and sources. Confirm that the reads
  establish the absence of applicable requirements; an ambiguous not-found,
  permission error or incomplete ruleset inventory does not do so.
- Reconcile these sources with all three current-head inventories above. If no
  workflow, external provider or required check applies and no matching run is
  pending or failed, record **no applicable CI**, the head, and the evidence
  used. This satisfies the CI evidence path without calling unrun checks
  passed. Re-read after a head or relevant configuration change.

If an expected check can still register, keep the verdict pending; a missing
required check is not a pass. Diagnose a persistent gap from configuration and
workflow evidence; elapsed time alone proves neither absence nor failure. A
denied, malformed, truncated or failed read leaves the verdict unknown.
Report a genuine missing capability or external prerequisite with its evidence
and resume path; do not label a timeout as one.

Process durability is not session resumption
--------------------------------------------

The common structured owner continuation is separate from the persistent CI
service and detached currency service. Retain it during CI waits; on a wake,
inspect before renewing any service. Its state records the PR, branch,
window/service identities, next unfinished action, authority references and
holds. A service result that actually reconciles the watch is checkpointed;
an unrelated user question alone does not postpone the fallback. An unchanged
look has no chat reply, toast, repeated status comment or "still watching"
message. Answer direct user questions first; report meaningful progress,
changed required human contributions and whole-operation completion concisely.
Once CI is terminal, a stale CI wake reads current state and continues the
current phase, not a new old-head wait.

Runtime timers stop on session shutdown; the same session can restore saved
deadlines on resume, but no agent monitors across shutdown. A service can
outlive shutdown but cannot launch or resume an agent. A live idle or parked
owner retains its continuation. If registration or checkpoint fails, diagnose
and keep supervising through service completion while possible; report the
exact continuation gap.

On an owner turn, inspect the maintenance service and take `pr`'s currency
checkpoint before assessing readiness. Attempt base updates even when
current-head CI is in flight; assess CI on the resulting head after an update.
Resolve mechanical conflicts and service failures under the existing
undertaking rules; ask only for a genuine semantic decision or missing external
prerequisite. Merge, close, completion, a genuine human-only stopping point and
user stop stop the matching watch and owned services. A stale wake cannot clear
a hold or restart a stopped watch; only a later explicitly authorized workflow
may register a fresh run using the canonical key plus `:run:<uuid>`.



Review history, publication, and threads
========================================

Read the history needed under `SKILL.md`: new reviews and replies, open
findings, and relevant prior decisions, using the previous checkpoint or
links. The calls below support reconstruction when incremental state is
missing, including after a resume, or when a dispute requires it. Paginate
needed results to completion. A GraphQL `PullRequest.reviewThreads` query
provides `id`, `isResolved`, `isOutdated`, comments, replies, revisions, paths,
lines, and bodies. A REST comments page does not supply the `PRRT_…` node ID
needed to resolve a thread.

After review, check current-head content and any inline anchors. Preserve the
reviewed revision if the head moved, and obtain applicable new review for
behavioral changes. Check the existing record before posting to avoid duplicate
findings. Use native publication, or put line-specific findings in `review.json`
and submit a review, for example:

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
"/repos/{owner}/{repo}/pulls/{n}/reviews", "--input", "review.json"] })`.
`COMMENT` is an example, not an evidence gate. Use `start_side` and
`start_line` for a valid range. Cross-cutting or clean results can use the
summary without `comments`. If inline publication is unavailable, record
findings with clear file and code references in a pull-request comment through
`daily_driver_gh_write({ args: ["pr", "comment", <number>, "--body-file", <path>] })`.
Never invent an anchor. If no durable route works, retain the findings and
report publication as incomplete.

| Operation | Call |
| --------- | ---- |
| Read reviews | `gh api --paginate /repos/{owner}/{repo}/pulls/{n}/reviews` |
| Read threads | paginated `gh api graphql` query of `PullRequest.reviewThreads` |
| Publish review | `daily_driver_gh_write({ args: ["api", "--method", "POST", "/repos/{owner}/{repo}/pulls/{n}/reviews", "--input", "review.json"] })` |
| Publish result or summary | `daily_driver_gh_write({ args: ["pr", "comment", <number>, "--body-file", <path>] })` |
| Reply on a thread | `daily_driver_gh_write({ args: ["api", "-X", "POST", "/repos/{owner}/{repo}/pulls/{n}/comments/{comment_id}/replies", "--input", "reply.json"] })` |
| Resolve a thread | `gh api graphql` with the `resolveReviewThread` mutation |

The identifier trap `SKILL.md` states applies to the last two: the mutation
takes the thread's `PRRT_…` node ID, while reply takes the comment's numeric
ID. Keep returned review or comment links with the covered revision and
dispositions so later rounds can find the evidence without republishing it.
The wrapper adds and deduplicates ordinary provenance for review and reply
bodies; do not add a new block to `review.json` or `reply.json`.
