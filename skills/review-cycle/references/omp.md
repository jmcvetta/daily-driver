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

**A bounded, supervised `gh pr checks --watch`.** `github` is optional and
disabled by default on Omp, so use a named Bash service. Omp distinguishes the
Agent Hub TUI ([`agent-hub.md`](omp://agent-hub.md)) from model-facing
process control ([`bash`](omp://tools/bash.md),
[`write`](omp://tools/write.md), and [`wait`](omp://tools/wait.md)). Start
the service once with `bash` in service mode; do not pass `async` or `timeout`,
which that mode rejects:

```text
{
  "command": "printf 'ci-watch-started sha=<sha> deadline=<utc>\\n'; exec timeout --signal=TERM --kill-after=5s <remaining>s gh pr checks --watch <pr> --repo <owner>/<repo>",
  "name": "ci-<pr>-<short-sha>",
  "cwd": "<task-worktree>",
  "ready": {"log": "ci-watch-started"}
}
```

`ready.log` matches only the launch marker printed before the watcher starts.
It means the service command launched, not that CI passed or a check registered.
The `exec` preserves the watcher's exit status as the service's status.

The service command uses GNU coreutils `timeout`. It owns the fifteen-minute
deadline, sends `TERM` at the cap, then sends `KILL` after five seconds if the
watcher has not exited. Exit `124` marks expiration; `137` is a `SIGKILL`
status. Every nonzero exit is non-green. Read all three sources after the
watcher exits.
If `timeout` is not installed, stop before starting an unbounded watch and
report the missing deadline utility.

After the service reports ready, inspect `read proc://<name>`. If it has
already exited, read all three CI sources immediately; do not request persistence
or restart it. Otherwise request persistence with `write proc://<name>/mode`
and content `persist`, then inspect `read proc://<name>`. Persistence is
required because the owning session may end during the wait. If the mode write
fails, inspect the service once: if it is still running, stop it with
`write proc://<name>/kill`; report the exact failure either way. Also stop it
if status does not confirm `persist=true`. Do not leave a session-scoped
watcher running and call it durable. Do not use `detached`: the bounded
watcher needs to survive Omp clients, not broker shutdown.

Before a start, inspect `read proc://<name>` and reuse an existing watcher.
Starting a service with a live name restarts it and resets its deadline. A
resumed session must not restart it. `read proc://<name>` reports its status
and logs. The `wait` tool has no arguments; use it only when there is no other
work. It returns on a caller-owned service completion or an interrupt, and
has a single thirty-minute safety cap. The watch itself enforces the stricter
fifteen-minute cap. Completion delivery and persisted service state do not
reopen or resume a terminated Omp session; after resuming, inspect the service
and continue from the observed state. Do not assume a separate owner-scoped
completion replay.

| Half | Call |
| ---- | ---- |
| The PR check rollup | Named `bash` service above; inspect with `read proc://<name>`, stop with `write proc://<name>/kill` |
| The check runs | `gh api --paginate /repos/{owner}/{repo}/commits/{sha}/check-runs` |
| The commit statuses | `gh api --paginate /repos/{owner}/{repo}/commits/{sha}/status` |
| The workflow runs | `gh api --paginate '/repos/{owner}/{repo}/actions/runs?head_sha={sha}&per_page=100'` |
| One workflow run | Named `bash` service, `gh run watch <run-id> --repo <owner>/<repo>`, below |

The watcher is the wake; the three reads are the verdict. `gh pr checks
--watch` stops when no rollup entry is pending, and it reads the rollup, not
the workflow-run inventory. A workflow whose jobs have not registered is
invisible to it, so its exit proves nothing about CI. Read all three sources,
every page, after `wait` returns or a resumed session finds the service
exited. `reported` is their union, not the output of `gh pr checks` alone.

**The deadline is absolute and recorded.** When the wait begins, capture the PR
head SHA and the deadline (start plus fifteen minutes, as a UTC timestamp), and
print both in the launch marker: `printf 'ci-watch-started sha=<sha> deadline=<utc>\n'`.
The service log is the recovery record. Every later watch for that head, a
resumed session's included, runs `timeout` with the seconds remaining to that
recorded deadline, never a fresh `900s`. A head that moved voids the old
verdict and starts a new wait for the new head.

**Workflow runs.** Do not filter the inventory by `status`. Keep a run only if
its `head_sha` equals the captured SHA, and drop one only when its
`pull_requests` array is non-empty and names other pull requests; an empty
array proves nothing, and a branch name alone never ties a run to the head.
Count the current attempt (`run_attempt`) only. A run is terminal only when
`status` is `completed` and `conclusion` is non-null. `queued`, `requested`,
`waiting`, `pending`, `in_progress`, null and unrecognized statuses are
nonterminal, whether or not the run has registered a check.

**A nonterminal run after the check watcher exits** gets its own service, with
the original deadline's remainder:

```text
{
  "command": "printf 'run-watch-started run=<run-id> attempt=<n>\\n'; exec timeout --signal=TERM --kill-after=5s <remaining>s gh run watch <run-id> --repo <owner>/<repo>",
  "name": "ci-<pr>-<short-sha>-run-<run-id>-<attempt>",
  "cwd": "<task-worktree>",
  "ready": {"log": "run-watch-started"}
}
```

Apply the same persistence, status inspection, reuse and cleanup rules as the
check service. Do not add `--fail-fast`, an unmanaged job or a `sleep`. Fine-grained
personal access tokens cannot run `gh run watch`; an unavailable watch is a
reported observation blocker, never completion. Exit 0 from `gh run watch`
without `--exit-status` can follow a failed run, so it is a wake only.

After any watch finishes, re-read the head and all three sources. A newly
observed active run blocks completion and receives only the remaining time.
Terminal failures are facts for `Fix, answer, resolve, push`; they never
satisfy the green gate and are not a reason to wait on.

**An empty or partial registration is a stop.** `gh pr checks --watch`
returns when the PR rollup is empty; a process that has already exited cannot
observe a future first check, however durable its completion is. Zero check
runs, an empty `statuses` array and no workflow run therefore mean nothing has
registered. A nonempty successful subset does not prove that all expected CI
has registered: where repository context names a workflow or check that has not
registered, the observation is incomplete. Reject both and report them; do not
call either green, add a fixed grace period, or hide an unbounded poll behind
the word *waiting*. Where the observable inventory is terminal and no known gap
remains, report the observed results, not a guarantee about workflows that
have not appeared. This is the partial watch exception `SKILL.md` names. A
repository known not to post commit statuses has no status half, but that fact
must be known rather than inferred from this first read.

**A failed, unauthorized, truncated or malformed read is not an empty
success.** At the deadline, stop and name the remaining runs and checks, their
IDs and statuses, and each registration gap. Do not review and do not post a
completion notice. On resume, inspect the existing services and their recorded
deadline; never restart a live service to extend the cap.

No `sleep`, subscription, timer, or unmanaged Bash job belongs here. The
named services are supervised by Omp, and GNU `timeout` enforces the
fifteen-minute cap.

Process durability is not session resumption
--------------------------------------------

**`daily_driver_schedule` is an in-process managed timer.** Managed timers are
unref'd and cleared on `session_shutdown`, so a reminder dies with the
session. Use one only for a follow-up inside the current session. It cannot
replace the named CI service. Its pair is `daily_driver_cancel_schedule`:
a wait that must not have a follow-up fire into the review borrows the slot
by cancelling the armed follow-up, and the owner re-arms with
`daily_driver_schedule` after the wait.
An armed reminder does not lapse, it fires: left pending, it injects *read
the checks again* as a follow-up in the middle of the review, restarting a
wait on a run that finished. On this harness `undertake`'s `Keep it current`
watch is the detached `keep-current-<number>` service, not a timer, so the
wait here borrows nothing from it — the loop's floor is what keeps a merge
from restarting a run in flight.

A persistent Omp service can outlive the session, but it does not launch or
resume one. Its status and logs remain the recovery record. The source reads
and review still need an agent turn. A resumed session inspects the same
service name and bases its next action on its current state.

**The completed watch answers CI, not branch currency.** The base branch may
move while the session is away, and the CI watcher does not watch it. After a
resumed owner inspects the service, the base-currency read comes first —
`undertake`'s [`omp.md`](../../undertake/references/omp.md) names the read and
the answers — and a `BEHIND` answer goes to `Keep it current` before the round
continues. A green run on a head the base has since moved past is not current
work.

The never-empty wake slot —
[`0010`](../../../docs/notes/0010-the-wake-slot-is-never-empty.md) — binds
Omp's managed timer for the session's life, exactly as it binds Claude's: one
timer in the slot, cancelled before a wait borrows it, re-armed after. What
it does not do is outlive the session — the timer dies at `session_shutdown`.
The named CI service holds process work across that boundary; it does not
resume its owner.


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
