# Claude Code routes — review-cycle

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).


The review surface
==================

The default is the session's built-in **`/code-review`**, run against the pull
request with **`--comment`**. Honor an operator-selected independent method
under `SKILL.md`; credible existing human or agent review of the relevant
content can satisfy the stage without another invocation.

`--comment` publishes findings on the pull request as resolvable inline
threads. That is a useful native route, not a requirement that all evidence
use one account or a particular GitHub review event.

**The level is named on every invocation.** `/code-review` otherwise reuses
whatever level was typed last, in some other session, about some other diff.
`SKILL.md`'s `Name the level` is the rule; this is the surface that makes it
load-bearing.

If the CLI returns findings without publishing them, record them through the
fallback below. A durable pull-request comment is also suitable evidence when
it identifies the reviewed content and preserves findings and dispositions.


Fix-delta verification
======================

**Unavailable on `/code-review`, not on the harness.** `/code-review
--comment` reviews the pull request as a whole; it has no measured SHA-range
or finding-disposition input, so it cannot be represented as an independent
delta pass, and a second full review through it is not targeted verification.
When a new delta pass is needed, use one briefed subagent through the `Agent`
tool, unless an operator-selected independent method applies. Existing
independent human or agent review covering the delta can also satisfy it.
Give the reviewer the pull request, base branch, prior reviewed revision,
current revision, relevant original findings and dispositions. Tell it in the
dispatch that its brief is the complete contract and that it must not load
`review-cycle`. Require a comparison of relevant pull-request content at those
revisions, excluding base-only changes, and inspection of affected callers.
Comparing the three-dot diffs is one way to establish that delta; commit
ancestry alone is not.
The reviewer reports whether implemented findings are solved and any concrete
regressions in the delta. It must not perform a full-PR audit or solicit style
work. The author records the independent result, never substitutes a verdict.

Publish new findings through the routes below. Link the result or use
`mcp__github__add_issue_comment` for a concise account of the checked content
and fixes, outcome, and any remaining defects or coverage limits. Preserve
enough prior results to recognize repeated unresolved defects and failed
approaches. No fixed verification fields, empty values, pass counter, usage
data, or reviewer-transcript inspection are required. A failed or incomplete
dispatch is not a clean result. Published records use ordinary `provenance`.

The wait
========

**Nothing in the Claude toolkit blocks until CI reports**, so the wait was once
a poll: read the checks, wake two minutes later, read again. The poll is still
here, as the backstop rather than as the mechanism.

Four parts, and the last one is not optional: a wait that subscribes and arms a
timer has two things running that outlive it.

Subscribe
---------

- **Subscribe** with `mcp__github__subscribe_pr_activity`, once, before the
  first read. CI results then arrive as `<wake reason="external-event">`
  envelopes that start a turn on their own — no interval to tune, and a green
  run is answered in the seconds after it goes green rather than at the next
  poll.
- **Read the tool result.** Where a PR Steward already watches the pull
  request, the call succeeds and the events go to the steward instead — the
  result says so. That is the case with no subscription in it, and the backstop
  is the whole wait.
- **Its absence is its own condition**, not `send_later`'s. A session can hold
  one call and not the other, so a surface without the scheduler may still have
  the subscription and should still take it. There is a
  `mcp__Claude_Code_Remote__subscribe_pr_activity` with the same contract;
  where both exist, use the GitHub one, and use one namespace throughout.

The read
--------

- **Read** with `mcp__github__pull_request_read` — **both** `get_check_runs`
  and `get_status`. `SKILL.md` says why the union of the two is what *reported*
  means; these are the two methods that answer it.
- Webhook delivery is not a guarantee, which is why every wake ends in a read.
  The harness's own pull request guidance, delivered alongside the
  `subscription.created` event, says webhooks *"don't reliably deliver CI
  success, new pushes, or merge-conflict transitions"*.

The backstop
------------

- **Wake** with `mcp__Claude_Code_Remote__send_later`, two minutes out,
  carrying the instruction to read again — then end the turn. The scheduler is
  what brings the session back when no event does, which is what makes the wait
  survive a dropped webhook and a steward-held subscription alike. Two minutes,
  unchanged: the backstop is what bounds the worst case, so making it lazier
  because the subscription usually beats it would slow down exactly the case it
  exists for.
- **Exactly one timer, ever, and never none.** Keep the `trigger_id` the call
  returns: that is the session's one wake slot. **The test is whether the slot
  is empty, not what woke the turn** — a wake with the timer still in flight
  arms nothing, and a turn whose slot is empty arms one before it ends.
  Re-arming on every wake regardless puts a timer in flight per check that
  reports, each of which wakes and re-arms again, and a wait that spends more
  turns than the poll it replaced has replaced nothing.
  [`0034`](../../../docs/notes/0034-the-wake-slot-is-never-empty.md) is the
  decision, and the report behind it is a session that emptied the slot and
  slept through a green run.
  [`0011`](../../../docs/notes/0011-two-harnesses-one-skill-tree.md) scopes it
  to Claude Code, which is why the rule lives in this file: a harness without a
  durable wake has no slot to fill.
**A slot already occupied is the backstop.** A wait entered while the PR
maintenance timer is in flight — `pr`'s `Keep it current`, which holds one
for the life of the PR — arms nothing: that timer is two minutes out too, and
every wake ends in a read whatever the wake was for. Note whose it is, because
`End the wait` cancels the timer in the slot and hands the slot back to `pr`.

End the wait
------------

At each fifteen-minute observation-window boundary, read the head and both CI
sources again. Nonterminal work renews the window with the existing single
timer and subscription; do not ask the user to restart monitoring. Expiration
alone is not a human blocker. A changed head invalidates earlier conclusions.
Diagnose failed observation routes and retain supported continuation while
permitted work remains.

Both halves stay active across window renewals. End this wait only when CI
has reported, no applicable CI is established under `SKILL.md`, or a genuine
blocker or user stop requires it:

- **Cancel the timer in the slot** with
  `mcp__Claude_Code_Remote__delete_trigger` — the backstop this wait armed, or
  `pr`'s cadence timer it borrowed under `The backstop`. An armed `send_later`
  does not lapse, it fires: left pending, it injects *read the checks again*
  as a user turn in the middle of the review, restarting a wait on a run that
  finished.
- **Unsubscribe** with `mcp__github__unsubscribe_pr_activity`. The subscription
  is this wait's, taken for it and dropped with it — the next wait on this pull
  request takes it again, and the call is idempotent. Left standing it is the
  round's own echo chamber, waking the session for every thread the round posts
  and every reply it writes.
- **Hand the slot back to `pr`**, where its `Keep it current` watch remains
  active. The wait does not arm that timer itself: `pr` arms it under its own
  rule, before the turn ends, so a check-in cannot fire into the round this
  cancel was clearing the way for. What this bullet forbids is standing down
  instead — no timer and no subscription, on a pull request `pr` is still
  driving, which is the session asleep through a green run that
  [`0034`](../../../docs/notes/0034-the-wake-slot-is-never-empty.md) records.
  **A wait with no active PR-maintenance watch arms nothing.** A round run on
  its own — without a `pr` watch — has no cadence to resume and no step that
  would ever end one, so a check-in armed here would wake a session that has
  stopped driving anything. This wait owns the reading loop, never the
  standing watch.

A laptop with neither
---------------------

Where a Claude session has neither the subscription nor the scheduler, the wait
is what that surface can block on, with a human watching the terminal:
`gh pr checks --watch <number>` where the CLI is installed, inside the Bash
timeout. Failing that, this is the surface `SKILL.md` says cannot wait: read
the checks once, apply its absence-evidence rule, and report any pending or
unknown result and the continuation limit. Proceed with review of the stable
pushed head; readiness requires green CI or established no-applicable-CI evidence.


Review history, publication, and threads
========================================

Read the relevant new reviews, comments, replies, open findings, and prior
decisions using the previous checkpoint or links. `pull_request_read` provides
`get_reviews`, `get_review_comments`, and `get_comments`. Follow all pages
needed for that context. Reconstruct resolved and outdated threads as well
when reliable state is missing, including after a resume, or a dispute
requires it; do not reread all history on every round.

`/code-review --comment` is the native publication route. Confirm that its
result was recorded and identifies the reviewed content. Compare returned
identifiers or links with the existing record to avoid duplicate publication.
The GitHub event type and publishing account do not determine whether the
review is independent or current.

For locally returned findings, a submitted review can be created with `curl`
and the ambient `GITHUB_TOKEN` on a web worker, or `gh api` on a laptop,
through `POST /repos/{owner}/{repo}/pulls/{n}/reviews`. An example JSON body has
`event: "COMMENT"`, `commit_id: <reviewed-sha>`, summary `body`, and a
`comments` array carrying `path`, `side`, `line` (and `start_side` /
`start_line` for a range), and finding body. The summary can carry clean or
unanchorable results. `COMMENT` is an example, not an evidence gate.

Check freshness and any inline anchors before publishing. If the head moved,
preserve the reviewed revision and compare relevant content; unchanged content
can retain evidence, while behavioral changes need applicable new review.
If inline publication is unavailable, use `mcp__github__add_issue_comment` with
clear file and code references for findings. Never invent an anchor. A failed
durable publication is reported as incomplete, with findings retained.
Apply ordinary `provenance` to each published artifact.

| Operation | Call |
| --------- | ---- |
| Read review history | `mcp__github__pull_request_read`, `get_reviews`, `get_review_comments`, and `get_comments` |
| Native publication | `/code-review` with `--comment` |
| Fallback publication | `curl` with `GITHUB_TOKEN`, or `gh api`, to `POST /repos/{owner}/{repo}/pulls/{n}/reviews` |
| Publish result or summary | `mcp__github__add_issue_comment` |
| Reply on a thread | `mcp__github__add_reply_to_pull_request_comment` |
| Resolve a thread | `mcp__github__resolve_review_thread` |

The identifier trap `SKILL.md` states applies to the last two: resolve takes
the thread's `PRRT_…` node ID, reply takes the `#discussion_r…` number from the
comment's `html_url`. Findings recorded in a summary instead of a thread
receive their substantive dispositions in that record or a linked follow-up.
