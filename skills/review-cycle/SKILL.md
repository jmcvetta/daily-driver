---
name: review-cycle
description: >-
  This skill should be used whenever a pull request is being reviewed and that
  review is then answered — including when the user says "/review-cycle",
  "review the PR and fix what it finds", "address the review feedback", "reply
  to the review comments", "resolve those threads", or "does that need another
  review?", and on any call to a harness's review surface aimed at a pull
  request — before invoking a pull-request review, replying to or resolving
  a review thread, or waiting for a pull request's checks. Supplies the CI
  wait on the pushed head, the review invocation and its level, the protocol
  every finding is answered under, and the test for whether a later push earns
  a second round. Not for opening a pull request or bringing one up to date —
  that is `pr` — nor for marking a draft ready, which is the caller's gate.
---

# Review cycle

One round: **review, answer, and decide whether it goes again.** A pull request
is reviewed once per diff, every finding it raises is closed out, and a push
that only answered the review does not buy a second review.

The analysis is the harness's own review surface, and this skill does not
supply it. What it supplies is the four things around it — the wait for CI, the
level, the thread protocol, and the re-review test — none of which any review
surface has an opinion about, and all four of which are the ones that go wrong.

**The routes are per harness, and they live beside this file.** Every operation
below is named in words here and resolved to a call there:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi,
[`references/codex.md`](references/codex.md) for Codex. Read the one for the
harness in use, and read it before the wait rather than during it — the wait is
where the harnesses differ most, and one of them cannot wait at all.

Callers keep their own gates. `undertake` runs this round between its `Open the
draft` and `Ready for review` steps, runs it again where its `Keep it current`
earns one, and owns whether the pull request then goes ready — including the
return to draft while that later round runs. Nothing here marks a draft ready
or merges anything.


The round
=========

| # | Stage | Owner |
| - | ----- | ----- |
| 1 | `Review the head` | the harness's review surface |
| 2 | `Fix, answer, resolve, push` | this skill |
| 3 | `Does it go again?` | this skill |

**Every stage has a name, and the name is how it is cited** — here and in
`undertake`, whose `Review the head` and `Fix, answer, resolve, push` steps are
the first two of these and carry the same names for that reason. Its
`Ready for review` is its own, not a third stage of this round. The numbers
order the round and do nothing else, because a number moves when a stage is
inserted and a name does not.
[`0005`](../../docs/notes/0005-steps-are-cited-by-name.md) is the decision.

**A round entered on findings that already exist starts at `Fix, answer,
resolve, push`.** Half the register arrives that way — *"address the review
feedback"*, *"reply to the review comments"*, *"resolve those threads"* — and
the findings are then a human's, a bot's, or an earlier round's.
Running `Review the head` over them would post a fresh set on top of the ones
somebody asked to have answered, which is worse than not firing at all.
`Review the head` is for a head nobody has reviewed yet; `Does it go again?`
still decides what happens after.


1 — Review the head
===================

**Wait for CI to report on the pushed head first.** A pull request opened
seconds ago has its checks queued, and a queued check is not a passing one — a
review that reads it as either answer is reviewing the runner, not the code.
The wait ends when every check has reported, whichever way it reported: a red
check is a fact about the branch, not a reason to hold the review, and
`Fix, answer, resolve, push` is where it is answered.

Then **run the harness's review surface against the pull request**, and take
what it raises as the round's findings. The reference file names the surface
and the flags it is invoked with.

How to wait
-----------

**The mechanism is the harness's, and the harnesses differ.** One blocks until
the checks report; one cannot block at all and waits by waking itself; one does
neither, and *a surface that can neither block nor wake itself cannot wait*
below is what it does instead. The reference file has the calls and the
discipline each mechanism needs. What follows holds whichever one is in use.

- **Every wake ends in a read**, and the read is what decides. An event is a
  wake, never a verdict — a harness that delivers CI results as events does not
  guarantee delivering them.
- **Read the checks and the commit statuses both**, because they answer from
  different endpoints and a repository can report through either. The Checks
  API is what GitHub Actions writes to; commit statuses are what an external CI
  service, a coverage bot or a DCO check still posts. *Reported* is the union
  of the two. Both answer for the head commit of the pull request, which is the
  commit the checks are running on: that SHA is the key they are looked up by,
  it does not move while they run, and nothing here is waiting for it to.
- **An empty answer is not an answer.** Nothing from either endpoint, on a head
  pushed seconds ago, means nothing has registered yet rather than that
  everything passed — *every check has reported* is otherwise vacuously true of
  a pull request nothing has looked at. Keep waiting, and let the cap decide.
- **A wake that is not about a check is still just a read.** The round is its
  own loudest source of the other kind: a review that posts a thread per
  finding, and a reply to every one. None of that is a check reporting, so none
  of it moves the wait — read, find nothing changed, and go on with what the
  turn was doing. A wake arriving after the wait is over is a no-op for the
  same reason.
- **Cap the loop at fifteen minutes.** On the cap, stop and name the checks
  that have not reported. Do not review: an unreported check is the thing this
  wait exists not to guess at, and a check stuck for fifteen minutes is a
  report to the user rather than a longer wait.

**Never a `sleep`, in the foreground or in the background.** A sleep is a
timer, not a test of the thing waited on — it expires while the checks are
still queued as readily as it expires long after they went green. Backgrounded,
it is also the failure this mechanism was written for: a job named *"Wait ~3
minutes for CI"* that sits until it times out and never brings the session back
to the loop.

**And no shell wait at all where the session is unattended**, regardless of
which command-line clients are installed. The two shapes fail differently and
both fail: a blocking watch in the foreground is bounded by the Bash tool's
own timeout, and refused outright on a surface that blocks `sleep`; a
backgrounded one is not bounded by anything and cannot wake the session, which
is the report this mechanism answers.
[`0006`](../../docs/notes/0006-waiting-for-ci.md) is the decision, and carries
what was rejected with it.

**A surface that can neither block nor wake itself cannot wait.** Read the
checks once, and where they have not all reported, say so and stop. A wait a
session only claims to perform is worse than the stop. Whether the surface in
use is one of these is the reference file's answer, not a guess made here —
and one harness answers yes for every unattended session on it, so this is the
ordinary path there rather than the degraded one.


Name the level
--------------

**Where the review surface takes an effort level, name it; never inherit the
remembered one.** `medium` by default, `high` where the diff is large, or where
it touches authentication, cryptography, access policy, or a data migration.
Naming it is what makes two rounds on one branch comparable — a surface that
remembers a level otherwise reuses whatever was typed last, in some other
session, about some other diff.

**Nothing deeper is selectable here.** `xhigh` and `max` belong to the author,
who names one in the moment and unambiguously. The round is unattended and it
runs often, so a rule reaching for the deepest levels spends the author's quota
on every diff that matches it, round after round, with nobody watching the
bill. Sensitivity read from the diff is guessed from vocabulary besides — it
fires on a renamed CI job, and misses the one-line change to a comparison that
decides access. At `high` that guess is cheap and worth making. Above it, the
same guess is not.

**Where the surface takes no level, the round names the surface and nothing
more**, and the depth judgement is the surface's. The two rules above then have
nothing to bind: they exist because a level can be remembered, and a surface
with no level remembers none. The reference file says which case the harness in
use is.

A reviewer, not a bare subagent
-------------------------------

**The reviewer is a named surface the round chose, never a bare subagent.** A
bare subagent is an ad-hoc dispatch with no rubric: it inherits nothing, has no
level anybody chose, and posts nothing — its findings die in the transcript,
and `Fix, answer, resolve, push` has nothing to answer. The reference file
names the surface for the harness in use, and it is the only thing this stage
dispatches.

**Findings that land on the pull request survive the session**, and that is
what makes them the record of why the branch was judged ready. They arrive as
resolvable review threads, inline on the diff, where the reply-and-resolve of
`Fix, answer, resolve, push` is the ordinary path rather than a hoped-for one.
[`0001`](../../docs/notes/0001-built-in-review-surface.md) §4 records what was
measured, and the reference file says whether the harness in use lands them
that way.

**Where they do not**, `Fix, answer, resolve, push` degrades: the round carries
the findings itself, from the surface's result, and *resolve* reads as
*answered* — in this file **and in the caller's gate**, where a bullet asking
for no unresolved thread would otherwise be a condition the round can never
satisfy. A surface that posts plain issue comments degrades the same way, to
reply-only. Say so once, and re-measure into `0001` rather than leaving the
next round to rediscover it.

Record the head SHA
-------------------

**Record the head SHA you reviewed.** `Does it go again?` measures its test
from it, and nothing else records it.


2 — Fix, answer, resolve, push
==============================

Every finding gets a verdict, on its thread, and the thread is closed:

1. **Implemented** — fix it, reply saying so, resolve the thread.
2. **Rejected** — reply with the reason, and resolve it anyway. A rejection is
   an answer; only silence is not.
3. **Deferred** — only where the user asks for it. Claude does not propose a
   deferral: `judgement-call` names "leave a TODO" as the option that is never
   a real one, so a deferral Claude offers is the noise that skill deletes.
   When the user does defer, reply naming what was deferred and to where, then
   resolve — an open thread would claim the question is still live.
4. **A repeat finding** — a reviewer opening a new thread for something already
   rejected in an earlier round — is resolved with the same message as before.
   A fresh variation invites a fresh argument over a question that was already
   answered. This one is live precisely because `Review the head` can run again
   and re-raise what this stage rejected.
5. **Never left open silently.** The rule the other four exist to serve.

Every reviewer is the same protocol — Claude's own findings, a human's, a
bot's. None of it is reviewer-specific.

**It is harness-specific.** The threads are a GitHub review surface, and a
harness whose reviewer leaves no threads has none to answer or resolve: the
round then carries the findings and the commits are the record.
[`0011`](../../docs/notes/0011-two-harnesses-one-skill-tree.md) is the
decision.

The reply
---------

Verdict-first, concise, technical. A reader skimming twenty threads should
never have to parse a paragraph to learn whether the finding was implemented or
rejected. No thanks, no apologies, no restating the finding back at the
reviewer, and no poetry — verse attaches to the pull request body, never to a
finding somebody has to act on.

A rejection carries its reason and stops. *"Rejected — `n` is bounded by the
caller's `len(items)` check at `loader.go:88`"* is a complete reply; softening
it into a discussion reopens the thread the rule just closed.

The clients, and the identifier trap
------------------------------------

Three operations — **read the review threads, reply on one, resolve one** —
and the client that performs them differs by harness. The reference file has
the calls. The identifiers below are GitHub's, so the trap is the same
whichever client makes the call.

**The two calls take different identifiers, and only one of them is a field.**
Measured 2026-09-06: resolve wants the thread's `id`, a `PRRT_…` node ID, read
directly. Reply wants a number that appears nowhere as a field — the
`#discussion_r…` suffix of the comment's `html_url`, so
`…/pull/25#discussion_r3943994364` means `commentId: 3943994364`. Do not
substitute the thread ID into the reply: it is the identifier that *is*
present, which is why it gets reached for, and the call fails on a type that
looks plausible.

Then push
---------

A caller's CI gate reads the remote head, and a fix that never left the laptop
is not in it.


3 — Does it go again?
=====================

**Review once per diff.** `Fix, answer, resolve, push` usually puts commits on
the branch, so by the end of a round the head is usually not the one `Review
the head` read — and a rule that keyed on sameness would re-review on every
round that had anything to fix.

The test is therefore **provenance, not sameness**: take the head SHA recorded
at `Review the head`, and classify every commit made after it.

- **Answering** — a review finding, a review thread, a lint bot, a red check.
  These do not start a new round, however many of them there are. Answering a
  review is not new work, and re-reviewing the answer is the loop this rule
  exists to cut.
- **Changing what the code does** — new feature work, a scope addition, a
  conflict resolution that rewrites the branch's own files. This is a new diff.
  `Review the head` runs again over it, once, and its head SHA becomes the new
  mark.
- **Neither** — a comment reflow, a changelog line, a merge from the base
  branch that leaves the pull request's own diff untouched. **Not a new diff.**
  What a base merge breaks, it breaks in the build rather than in the diff, so
  a red check is what reports it and `Fix, answer, resolve, push` is where it
  is answered.
  The default is not to go again, because `Review the head` reads the pull
  request, whose diff is three-dot: a clean base merge changes the head and
  changes nothing it would read. Reviewing it again would review
  byte-identical content, and on a base branch that moves often it would do so
  without end.

The classification is per commit and the categories do not compound: a round
that only ever answers ends with one review behind it, which is the point.

When the mark is void
---------------------

Where the branch's history is rewritten — a rebase, an amend, a squash — the
recorded SHA stops being an ancestor of the head and the mark is void. There
are then no commits "after it" to read, which is not the same as there being
none. Fall back to content: compare the pull request's diff against what
`Review the head` reviewed, and go again only if it has changed.


Where it stops and waits
========================

- **CI still running**, before `Review the head`. A wait, not a question —
  nothing is asked, and nothing proceeds on a check that has not reported.
  `How to wait` is the mechanism, and its fifteen-minute cap is where the wait
  turns into a stop that reports.
- **A finding whose fix is a real trade-off**, in the sense `judgement-call`
  gives that phrase: two defensible approaches differing in something the user
  owns. That skill owns the gate, and it is the gate for every question this
  round would otherwise ask. A finding whose fix the standard already picks is
  not one of these — fix it and say so.

Everything else runs through. No permission is asked to fix a finding, to
reply, to resolve, or to push.


Non-goals
=========

- **Does not open the pull request, and does not update it as a whole.** That
  is `pr`. This round starts from one that already exists.
- **Does not mark a draft ready, and does not merge.** Whether the round's
  outcome is enough to go ready is the caller's gate — `undertake` has one —
  and a skill that answered its own review is the wrong judge of it.
- **Does not fire on reading a review.** "What did the reviewer say about the
  retry loop" is a question; answer it, and do not start a round.
- **Does not minimise superseded comments.** That is `pr-threads`' other half,
  retired to the attic rather than shipped: it is a GraphQL mutation the GitHub
  MCP does not expose, reachable only from a laptop on a personal token.
