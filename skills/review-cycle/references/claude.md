# Claude Code routes — review-cycle

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).


The review surface
==================

The session's built-in **`/code-review`**, run against the pull request with
**`--comment`**.

`--comment` is what carries the findings out of the terminal and onto the pull
request. They arrive as **resolvable review threads**, inline on the diff under
a submitted `COMMENT` review — measured on live pull requests at `medium` and
again at `max`, CLI 2.1.263, 2026-09-07, and recorded in
[`0001`](../../../docs/notes/0001-built-in-review-surface.md) §4. The default
level is measured rather than assumed from a deeper level's result.

**The level is named on every invocation.** `/code-review` otherwise reuses
whatever level was typed last, in some other session, about some other diff.
`SKILL.md`'s `Name the level` is the rule; this is the surface that makes it
load-bearing.

If the CLI returns findings without a submitted review, publish them through
the fallback below. Plain issue comments are not an equivalent artifact.


Fix-delta verification
======================

**Unavailable on `/code-review`, not on the harness.** `/code-review
--comment` reviews the pull request as a whole; it has no measured SHA-range
or finding-disposition input, so it cannot be represented as an independent
delta pass, and a second full review through it is not targeted verification.
The route is a briefed subagent instead: dispatch exactly one, through the
`Agent` tool, carrying the bounded brief `SKILL.md`'s `Verify the fix delta`
requires — the pull request, base branch, full-review SHA, current SHA,
original findings, dispositions, and pass number. Require it to compare the
pull request's three-dot content at the reviewed SHA with its three-dot
content at the current SHA, exclude changes attributable only to the base
branch, and inspect affected callers. It reports only whether each
implemented finding is solved and any concrete regressions in that delta. It
must not perform a full-PR audit, solicit style work, or supply the verdict —
the session records the result from the subagent's report, never in place of
it.

Publish any findings it raises through this file's `Review history,
publication, and threads` route below, then record the pass with
`mcp__github__add_issue_comment`:

```text
Review verification
scope reviewed: <sha>
pass: <n>
verified: <sha>
findings: <finding ids and dispositions>
outcome: <clear|defects|incomplete|unavailable>
defects: <none|concise list>
wall: <open|reached>
usage: <exact value if exposed|unavailable>
```

`outcome: unavailable` stays reachable for a dispatch that genuinely fails —
the subagent returns nothing usable, or does not return at all — recorded as
such rather than guessed at; a working dispatch is not unavailable by design.
Never estimate usage when the invocation does not expose it.

Review-cycle completion notice
==============================

After a non-standalone round meets `SKILL.md`'s completion conditions and
`Does it go again?` starts no new full review, read the current head with `mcp__github__pull_request_read`, method `get`, and
conversation comments with the same tool, method `get_comments`. If no existing
comment starts with `## 🎉 Review cycle complete! 🎉` and names that head, post
the separate notice with `mcp__github__add_issue_comment`. Its body starts with
that heading, gives a short factual completion status, and names the completed
SHA. Re-read the head immediately before writing; a changed head does not
inherit the notice. A failed write is reported, never claimed.

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
  [`0010`](../../../docs/notes/0010-the-wake-slot-is-never-empty.md) is the
  decision, and the report behind it is a session that emptied the slot and
  slept through a green run.
  [`0011`](../../../docs/notes/0011-two-harnesses-one-skill-tree.md) scopes it
  to Claude Code, which is why the rule lives in this file: a harness without a
  durable wake has no slot to fill.
- **A slot already occupied is the backstop.** A wait entered while the
  caller's cadence timer is in flight — `undertake`'s `Keep it current`, which
  holds one for the life of the pull request — arms nothing: that timer is two
  minutes out too, and every wake ends in a read whatever the wake was for.
  Note whose it is, because `End the wait` cancels the timer in the slot and
  hands the slot back to that owner.

End the wait
------------

Both halves are running until something stops them, and neither stops itself.
On the wake that ends the wait — every check reported, however it reported, or
the fifteen-minute cap:

- **Cancel the timer in the slot** with
  `mcp__Claude_Code_Remote__delete_trigger` — the backstop this wait armed, or
  the caller's cadence timer it borrowed under `The backstop`. An armed
  `send_later` does not lapse, it fires: left pending, it injects *read the
  checks again* as a user turn in the middle of the review, restarting a wait
  on a run that finished.
- **Unsubscribe** with `mcp__github__unsubscribe_pr_activity`. The subscription
  is this wait's, taken for it and dropped with it — the next wait on this pull
  request takes it again, and the call is idempotent. Left standing it is the
  round's own echo chamber, waking the session for every thread the round posts
  and every reply it writes.
- **Hand the slot back to the caller**, where the caller keeps a standing
  cadence and the surface has the scheduler that cadence needs. The wait does
  not arm that timer itself: the caller arms it under its own rule, before the
  turn ends, so a check-in cannot fire into the round this cancel was clearing
  the way for. What this bullet forbids is standing down instead — no timer and
  no subscription, on a pull request the caller is still driving, which is the
  session asleep through a green run that
  [`0010`](../../../docs/notes/0010-the-wake-slot-is-never-empty.md) records.
  **A wait with no such caller arms nothing.** A round run on its own — no
  `undertake` around it — has no cadence to resume and no step that would ever
  end one, so a check-in armed here would wake a session that has stopped
  driving anything. This wait owns the reading loop, never the caller's watch.

A laptop with neither
---------------------

Where a Claude session has neither the subscription nor the scheduler, the wait
is what that surface can block on, with a human watching the terminal:
`gh pr checks --watch <number>` where the CLI is installed, inside the Bash
timeout. Failing that, this is the surface `SKILL.md` says cannot wait: read
the checks once, and where they have not all reported, say so and stop.


Review history, publication, and threads
========================================

Before reviewing, read `pull_request_read` with `get_reviews`,
`get_review_comments`, and `get_comments`. Follow every page or cursor until
the result is complete. Preserve resolved and outdated threads, replies,
review identifiers, and reviewed SHAs in the reviewer brief.

`/code-review --comment` is the native publication route. Confirm that its
result is a submitted `COMMENT` review with the reviewed SHA before treating
its threads as recorded. Compare the returned review and comments with the
history first; a resumed session must not post native findings twice.

Where the review surface returns findings but no submitted review, create one
with `curl` and the ambient `GITHUB_TOKEN` on a web worker, or `gh api` on a
laptop, through `POST /repos/{owner}/{repo}/pulls/{n}/reviews`.
The JSON body has `event: "COMMENT"`, `commit_id: <reviewed-sha>`, a summary
`body`, and a `comments` array whose entries carry `path`, `side`, `line`
(and `start_side` / `start_line` for a range), and finding body. The submitted
summary carries unanchorable or clean results. Validate the head and diff
anchors again immediately before this call. A missing token, GitHub rejection,
or head change leaves the findings intact and reports publication as incomplete.

The `/comments` fallback measured in `0001` demonstrates inline posting, not
this submitted-review aggregation; read the response and review history before
claiming the aggregation succeeded.

| Operation | Call |
| --------- | ---- |
| Read review history | `mcp__github__pull_request_read`, `get_reviews`, `get_review_comments`, and `get_comments` |
| Native publication | `/code-review` with `--comment` |
| Fallback publication | `curl` with `GITHUB_TOKEN`, or `gh api`, to `POST /repos/{owner}/{repo}/pulls/{n}/reviews` |
| Reply on a thread | `mcp__github__add_reply_to_pull_request_comment` |
| Resolve a thread | `mcp__github__resolve_review_thread` |

The identifier trap `SKILL.md` states applies to the last two: resolve takes
the thread's `PRRT_…` node ID, reply takes the `#discussion_r…` number from the
comment's `html_url`. The fallback creates a review, not a loose comment, so it
gives the summary and each finding one durable review record.
