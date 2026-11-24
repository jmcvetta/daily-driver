# Codex routes — review-cycle

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in [`claude.md`](claude.md),
Omp's in [`omp.md`](omp.md).

Two of the three parts carry over and one does not. The review surface and the
threads have calls; the wait has none that an unattended session may use, and
that is the stop below.


The review surface
==================

The default is the native app-server base-branch review from the checked-out branch:

```sh
python3 <daily-driver-root>/skills/review-cycle/scripts/codex-review.py <base-branch> --history <history-file>
```

The UTF-8 history file contains the relevant prior reviews, findings and
dispositions, reviewed revision, and current head. Use incremental context as
described below; include full history only when reconstruction is needed.
Store it in an owner-only file outside the checkout and artifacts. The helper
passes this as reference data, not instructions. Its standard output is the
complete native review result; retain it for publication. A nonzero exit or
missing result is an incomplete review, not a clean verdict.

The helper reads the checkout's effective `developer_instructions`, adds the
constitution without printing either instruction set, and starts a separate
review thread. It computes the Git merge base and uses a native custom review
target to request the committed three-dot comparison. Review history is
user-role reference data, not developer instructions.
This custom target is needed because Codex 0.160.0's base-branch review drops
preloaded user history. The helper does not modify Codex configuration.

The base branch must be a local ref. A commit or uncommitted review is not a
substitute for the round's base-branch comparison.

**It reviews the checkout, not the pull request.** There is no argument that
takes a pull request number, and nothing is fetched: the branch has to be the
one checked out, and its base has to be a ref this clone has. That is a real
difference from Claude Code, where the round can review a pull request it never
checked out.

**Review freshness is content-based.** The helper requests a committed
three-dot comparison against the computed merge base. A clean base merge
can retain existing review evidence when the relevant pull-request content
is unchanged; a new SHA alone does not invalidate it. Behavioral changes
require the applicable new review under `SKILL.md`. Reject findings about
unchanged base-only code as outside this pull request, with a reason; do not
widen the pull request to fix them.

**It takes no effort level**, so `SKILL.md`'s `Name the level` has nothing to
bind — there is no remembered level to override, and the depth judgement is the
surface's. `-c model_reasoning_effort=…` sets a config value for the run rather
than a level the surface remembers between runs, and reaching for it would be
this round choosing a depth by hand on every diff, which `Name the level`
refuses above `high` for the reason it gives there.

**Record returned findings durably on the pull request.** Give the reviewer
the relevant history, reviewed revision, and current head. Use the publication
routes below, with ordinary `provenance`. Neither a particular account nor a
GitHub review event type is required.

The app-server starts a separate agent review thread and is billed as one.
Honor an operator-selected independent method under `SKILL.md`. Existing
credible independent human or agent review can supply evidence for the
relevant content without another invocation.



Fix-delta verification
======================

**Unavailable on `codex exec review`, not on the harness.** It accepts a base
branch or one commit, not a reviewed-SHA/current-SHA range plus findings and
dispositions; `--commit <SHA>` would verify one commit, not a batch, and
neither substitutes for the required delta pass. When a new pass is needed,
use the delegation namespace's `multi_agent_v1` dispatch — the same route
[`skills/undertake/references/codex.md`](../../undertake/references/codex.md)
uses for `Implement` — unless an operator-selected independent method applies.
Existing independent human or agent review covering the delta can also
satisfy the pass.

Give the reviewer the pull request, base branch, prior reviewed revision,
current revision, relevant findings and dispositions. Require comparison of
the relevant pull-request content at those revisions, excluding base-only
changes, and inspection of affected callers. Comparing the three-dot diffs
is one way to establish the delta; commit ancestry alone is not. The reviewer
reports whether implemented findings are solved and any concrete regressions
in the delta. It must not perform a full-PR audit or solicit style work. The
author records the independent result, never substitutes a verdict.

Publish any new findings through the routes below. Link the result or use
`gh pr comment <number> --body-file <path>` for a concise account of the
checked content and fixes, outcome, and any remaining defects or coverage
limits. Preserve enough prior results to enforce `SKILL.md`'s
three-defect-pass limit. No fixed verification fields, empty values, wall-state
token, usage data, or reviewer-transcript inspection are required. A failed or
incomplete dispatch is not a clean result. Published records use ordinary
`provenance`.

The wait
========

**There is nothing here that waits.** Codex can neither block on the checks nor
wake itself after the turn ends, so this harness is the one `SKILL.md` names
under `How to wait`: *a surface that can neither block nor wake itself cannot
wait*.

So, unattended: **read the checks once and apply `SKILL.md`'s absence-evidence
rule.** If checks remain pending or absence is unknown, report the continuation
limit. Proceed with review of the stable pushed head; readiness requires green
CI or established no-applicable-CI evidence. The owner must resume the
readiness check when incomplete results can be observed.

| Half | Call |
| ---- | ---- |
| The check runs | `gh api /repos/{owner}/{repo}/commits/{sha}/check-runs` |
| The commit statuses | `gh api /repos/{owner}/{repo}/commits/{sha}/status` |

Both, because `SKILL.md` says *reported* is the union of the two, and one read
of each is the whole of the wait here.

What is not a wait
------------------

Three things look like one and are not. Each is written down because each is
what the next session will reach for.

- **`sleep_tool`.** Codex ships a sleep. `SKILL.md` forbids one outright, in
  the foreground and in the background alike: a sleep is a timer, not a test of
  the thing waited on, and it expires while the checks are still queued as
  readily as long after they went green.
- **`gh pr checks --watch <number>` in the shell.** A blocking foreground watch,
  bounded by the shell tool's own timeout rather than by the checks. It is the
  same case `claude.md` calls *a laptop with neither*, and it is allowed on the
  same condition: **a person is watching the terminal.** Unattended it is the
  shape [`0006`](../../../docs/notes/0006-waiting-for-ci.md) rejects.
  saved session, which is most of a durable wake and not the part that matters:
  something outside Codex has to fire it at a time. A wake built on `at` or on
  cron is a workaround; discuss it first only when it materially changes
  scope, behavior, security, maintenance burden, or owner cost.

There is no wake slot
---------------------

[`0034`](../../../docs/notes/0034-the-wake-slot-is-never-empty.md)'s
never-empty wake slot is Claude Code's rule and not this harness's, for the
reason [`0011`](../../../docs/notes/0011-two-harnesses-one-skill-tree.md)
scoped it there: a harness with no durable wake has no slot to fill. Codex is
the second harness that is true of, and it is true here more sharply than on
Omp — Omp at least blocks on the Actions runs, so its wait completes inside the
turn. This one does not wait at all.

`undertake` has no cadence or wake slot on this harness. Its owner-resume
catch-up obligation starts at `Open the draft` and continues before and after
`Ready for review` until the pull request merges, closes, or the user stops it.


Review history, publication, and threads
========================================

Read relevant new reviews and replies, open findings, and prior decisions
using the previous checkpoint or links. The calls below support reconstruction
when reliable state is missing, including after a resume, or when a dispute
requires it. Paginate needed results to completion; do not reread all history
on every round.

A GraphQL `PullRequest.reviewThreads` query provides `id`, `isResolved`,
`isOutdated`, comments, replies, revisions, paths, lines, and bodies. A REST
comments page does not supply the `PRRT_…` node ID needed to resolve a thread.

After review, check freshness and any inline anchors. Preserve the reviewed
revision if the head moved; compare relevant content and obtain applicable
new review for behavioral changes. Check the existing record before posting
to avoid duplicate findings. Use native publication when available, or put
line-specific findings in `review.json` and submit a review, for example:

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
review.json`. `COMMENT` is an example, not an evidence gate. Use
`start_side` and `start_line` for a valid range. Clean or cross-cutting results
can use the summary without `comments`. If inline publication is unavailable,
record findings with clear file and code references through
`gh pr comment <number> --body-file <path>`. Never invent an anchor. If no
durable route works, retain the findings and report publication as incomplete.
Apply ordinary `provenance` to every published artifact.

| Operation | Call |
| --------- | ---- |
| Read reviews | `gh api --paginate /repos/{owner}/{repo}/pulls/{n}/reviews` |
| Read threads | paginated `gh api graphql` query of `PullRequest.reviewThreads` |
| Publish review | `gh api --method POST /repos/{owner}/{repo}/pulls/{n}/reviews --input review.json` |
| Publish result or summary | `gh pr comment <number> --body-file <path>` |
| Reply on a thread | `gh api -X POST /repos/{owner}/{repo}/pulls/{n}/comments/{comment_id}/replies` |
| Resolve a thread | `gh api graphql` with the `resolveReviewThread` mutation |

The identifier trap `SKILL.md` states applies to the last two: the mutation
takes the thread's `PRRT_…` node ID, while reply takes the comment's numeric
ID. Keep returned review or comment links with the covered revision and
dispositions so later rounds can find the evidence without republishing it.


Provenance
==========

Codex 0.160.0: isolated loopback scripted-provider experiments with a non-empty
committed diff exercised `config/read`, `thread/start`, and `review/start`.
The custom review request carried synthetic operator instructions and the
complete constitution in developer context, with review history in user
context. The complete scripted review text returned to the caller. This proves
transport, not the quality or correctness of a model review.
