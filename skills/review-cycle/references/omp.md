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
pass: <1|2>
verified: <sha>
findings: <finding ids and dispositions>
outcome: <clear|defects|incomplete|unavailable>
defects: <none|concise list>
cap: <open|hit>
usage: unavailable
```

The task agent's result is independent evidence. The author writes this record
only after receiving it; it must not invent a verdict. Omp exposes no reviewer
token-usage value, so `usage: unavailable` is required.

The wait
========

**A supervised `gh pr checks --watch`.** `github` is optional and disabled by
default on Omp, so it is never this route. The essential `hub` tool owns a
`gh` process directly — not through a shell — and keeps its lifecycle visible
to the session:

| Half | Call |
| ---- | ---- |
| The PR check rollup | `hub start` runs `gh pr checks --watch <pr> --repo <owner>/<repo>`; `hub wait` on that name for exit with timeout: 900 |
| The check runs | `gh api /repos/{owner}/{repo}/commits/{sha}/check-runs` |
| The commit statuses | `gh api /repos/{owner}/{repo}/commits/{sha}/status` |

Name the process `ci-<pr>-<short-sha>`. Read the check runs and statuses only
after the supervised watch exits. The watcher is the wake; the two endpoint
reads are the verdict. `reported` is their union, not the output of `gh pr
checks` alone.

**The cap belongs to `hub wait`.** Start timing with that call. On its
fifteen-minute timeout, call `hub stop` on the same name, read both endpoints
once, and report every unreported check. A watcher exit with a failed check
still leads to the two reads: red is reported, not a reason to review without
the status half.

**An empty pair is a registration stop.** `gh pr checks --watch` returns when
the PR rollup is empty; it cannot observe a future first check, and Omp has no
durable wake for one. Zero check runs and an empty `statuses` array therefore
mean no check has registered. Reject that result and report it; do not call it
green or hide an unbounded poll behind the word *waiting*. This is the partial
watch exception `SKILL.md` names. A repository known not to post commit
statuses has no status half, but that fact must be known rather than inferred
from this first read.

No `sleep`, subscription, timer, or unmanaged Bash job belongs here. The
`SKILL.md` prohibition on an unattended shell wait remains: this is an Omp
supervised process with an explicit stop at the same fifteen-minute cap, not a
Bash command whose timeout ends the session's control of it.

There is no durable wake
------------------------

**`daily_driver_schedule` is an in-process managed timer, and a reminder dies
with the session.** Omp's own documentation says managed timers are unref'd and
cleared on `session_shutdown`. It is not a `send_later`, which survives the
session that armed it.

So the never-empty wake slot —
[`0010`](../../../docs/notes/0010-the-wake-slot-is-never-empty.md) — is
Claude's rule and not this harness's. It has nothing to hold. `hub wait`
completes the supervised watch inside the turn, so no wake is scheduled around
it, and a wake scheduled with nothing to do on it is the noise `0010` exists
to prevent.
Schedule with `daily_driver_schedule`, and cancel with
`daily_driver_cancel_schedule`, only where the round must hand the pull request
back to itself for a follow-up **inside the current session** — never as a
watch that outlives it.


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
