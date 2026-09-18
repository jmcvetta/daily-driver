---
name: review-cycle
description: >-
  Use this skill whenever a pull request is reviewed, alone or then answered —
  including "/review-cycle", "review the PR", "review the PR and fix what it
  finds", "address the review feedback", "reply to the review comments",
  "resolve those threads", or "does that need another review?", and before
  invoking a pull-request review, recording a review finding, replying to or
  resolving a review thread, or waiting for a pull request's checks. Supplies
  the CI wait on the pushed head, the review invocation and its level, a
  durable inline review record, the finding response protocol, bounded
  independent verification of fix deltas, and the test for whether a later
  push changes the full-review scope. Not for opening a pull request or
  bringing one up to date — that is `pr` — nor for marking a draft ready,
  which is the caller's gate.
---

# Review cycle

One full review per scope, then an independent fix-delta pass for every batch
of corrections pushed under it, until one comes back clean or three in a row
do not. Every finding is answered, and a behavioral fix is verified without
repeatedly auditing unchanged pull-request content. A standalone review records its
findings and stops; it does not turn into an implementation run.

The analysis is the harness's own review surface, and this skill does not
supply it. What it supplies is the six things around it — the wait for CI, the
level, the durable review record, the thread protocol, bounded fix verification,
and the full-review test — none of which any review surface has an opinion
about.

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
| 3 | `Verify the fix delta` | the harness's review surface |
| 4 | `Does it go again?` | this skill |

**Every stage has a name, and the name is how it is cited** — here and in
`undertake`, whose `Review the head` and `Fix, answer, resolve, push` steps are
the first two of these and carry the same names for that reason. `Verify the
fix delta` is independent verification, not another full review. Its outcome
is part of `Ready for review`'s gate. The numbers order the round and do
nothing else, because a number moves when a stage is inserted and a name does
not. [`0005`](../../docs/notes/0005-steps-are-cited-by-name.md) is the
decision.

**A round entered on findings that already exist starts at `Fix, answer,
resolve, push`.** Half the register arrives that way — *"address the review
feedback"*, *"reply to the review comments"*, *"resolve those threads"* — and
the findings are then a human's, a bot's, or an earlier round's.
Running `Review the head` over them would post a fresh set on top of the ones
somebody asked to have answered, which is worse than not firing at all.
`Review the head` is for a head nobody has reviewed yet; `Does it go again?`
still decides what happens after.

**A standalone review ends after `Review the head`.** It reads the history,
reviews the requested pull request, publishes a submitted review, and reports
the result. It does not enter `Fix, answer, resolve, push`, resolve its new
threads, alter draft state, or merge. A request to fix or answer existing
findings is not standalone and follows the relevant later stage.


1 — Review the head
===================

**Wait for CI to report on the pushed head first.** A pull request opened
seconds ago has its checks queued, and a queued check is not a passing one — a
review that reads it as either answer is reviewing the runner, not the code.
The wait ends when every check has reported, whichever way it reported: a red
check is a fact about the branch, not a reason to hold the review, and
`Fix, answer, resolve, push` is where it is answered.

First **read the complete review record**, then run the harness's review
surface against the pull request. The record and current head tell the reviewer
what has already been considered; the reference file names both the reader and
the publication route.

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
  **The exception is a partial watch that cannot observe registration and
  cannot wake itself.** Its reference must say so; it rejects the empty result
  and stops under *A surface that can neither block nor wake itself cannot
  wait*, rather than hiding an unbounded poll behind the word *waiting*.
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

Review record, not transcript
-----------------------------

**Every reviewer carries a bounded brief and a publication contract.** What
disqualifies a dispatch is not that it is a subagent — the constitution reaches
every subagent here, through `SubagentStart` and the `PreToolUse` hook on
`Agent`/`Task` — it is a dispatch with no rubric bounding what it reviews and
no route landing its findings as resolvable threads under a submitted
`COMMENT` review. What stays forbidden is a dispatch missing either half.

**At `Review the head` the reviewer is still the harness's named review
surface, and only that surface.** It supplies both by being named, along with
the effort level `Name the level` binds and the measured resolvable-thread
contract; whether a panel of briefed subagents should replace it is a
question this rule does not answer. `Verify the fix delta` is where a briefed
subagent is a reviewer: the reference file states its brief and its
publication route rather than leaving either assumed.

**Read the complete GitHub review history before each review.** Read submitted
reviews and every inline thread, including resolved and outdated threads, their
replies, and the recorded dispositions. Paginate to the end; the newest page
is not the history. Give the reviewer that history, the reviewed SHA, and the
current head rather than leaving the prior decision only in the author's
context.

**Every actionable line-specific finding is an inline thread in a submitted
`COMMENT` review.** The event is `COMMENT`: a review round states findings, and
approving or requesting changes is the human reviewer's verdict to give, not
this stage's. Anchor each finding to the reviewed commit, path, side, and a
valid diff line — or, across more than one line, a start and end that both fall
in the diff.
Use a suggestion block only where it makes the concrete replacement clearer;
it never replaces the explanation of the defect. A finding with no valid
anchor, and a clean review, goes in the submitted review summary. Never invent
an anchor.

**Use the surface's native publication where it has one; otherwise publish its
returned findings through the available GitHub route.** Read the surface output
and existing review record first, and compare against the recorded review
identifier rather than the finding text, so a resumed run does not post the
same review twice. A reviewer returning findings locally is not permission to
leave them in the transcript.

**Re-read the head and re-validate every anchor immediately before
publication.** The head can move while the review is being prepared, and an
anchor validated against the old diff then lands on the wrong line or is
rejected. Publication keeps the reviewed SHA it was produced against; it never
re-attributes findings to a head they did not review.

**A publication that does not complete is reported, never rounded up.** An
absent GitHub client, a changed head, an invalid anchor, a permission problem,
or a GitHub rejection each leaves the findings intact and the recording step
named as incomplete. Never claim a durable review.

**One finding has one conversation.** A repeated finding links to the earlier
thread and disposition rather than reopening the argument. A recommendation
that reverses a recorded decision names the decision and its new evidence or
changed constraint. A prior decision is evidence, not immunity from a
demonstrated defect.

**A local review with no pull request still returns its findings and says that
GitHub recording is unavailable.** It does not create a pull request to obtain
a record.

**Record the reviewed SHA, review identifier, findings, and dispositions on the
pull request.** That record defines the scope, links the summary and threads,
and gives a resumed session the evidence it needs to enforce the bound. The
harness route names the durable format.


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


Every reviewer uses this protocol — Claude's own findings, a human's, a bot's,
or locally returned output. GitHub threads are the durable record, so a
reviewer that did not create them is followed by publication rather than a
transcript-only degradation.

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

**Reading history, publishing the review, replying, and resolving are
harness-specific operations.** The reference file names their calls. The
identifiers below are GitHub's, so the trap is the same whichever client makes
the call.

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
is not in it. Batch every outstanding finding and CI correction before asking
for verification. Per-finding verification is prohibited.


3 — Verify the fix delta
=========================

**Verify a behavioral delta independently after the batch is pushed and CI has
reported for that head.** Passing CI does not replace this pass. A red result
does not approve the head or satisfy the caller's readiness gate.

Give one reviewer the recorded full-review SHA, current SHA, original findings,
and their recorded dispositions. It verifies that implemented fixes solve their
findings and do not regress affected behavior. It may read surrounding code and
affected callers. It must not restart a full pull-request audit, solicit style
work, or accept the author's verdict as verification. The harness route names
the concrete invocation.

Classify the pull-request content delta, not commit provenance. A change to
behavior, a contract, or a workflow rule requires a pass, including Markdown
that changes workflow behavior and fixes prompted by CI or bots. Pure formatting
does not. A clean base merge whose three-dot pull-request content is unchanged
does not. Mixed changes require a pass. This content comparison also applies
after a rebase, amend, or squash: a missing ancestor is never evidence of no
change.

**A pushed fix batch always earns the pass that confirms it.** Verification of
a pushed fix is never refused for having spent a budget: an unverified fix
sitting on a pull request is worse than the pass that would have read it, and
a caller left holding one has no way to reach its own gate. The bound below
counts what actually goes wrong — fixes that do not converge — rather than
passes as such.

**The loop ends on the first clean pass.** A pass that records concrete
defects earns one batched correction, pushed, with CI results obtained, and
one more targeted pass over that correction delta and its regression risk.
That repeats while the passes keep finding defects.

**Three consecutive passes that each record defects is the wall**, in the
sense the constitution's *When you hit a wall* gives it: the corrections are
not converging, and a fourth attempt is the push-through that rule forbids.
Stop there. Post the outstanding defects on the pull request, leave (or
return) the pull request in draft, keep the caller's watch armed, and say in
one line what is blocking. An incomplete pass and an unavailable reviewer
stop unattended progress the same way, and neither is approval.

The count runs from the first pass of the scope. A clean pass resets nothing,
because a clean pass ends the loop. Commits, resumes, rewrites, late bot
findings, and further CI fixes are not passes and do not move the count; only
a pass that records defects moves it. A materially changed scope runs `Review
the head` as a new full round and starts a new count; it does not disguise a
reset as a fix.

Rejected findings remain closed unless new evidence defeats the recorded
rejection. Repeating a rejected finding without that evidence is not a defect
and does not consume a pass.

Record every pass on the pull request: reviewed SHA, verified SHA, pass number,
original findings and dispositions, outcome, actionable defects, and whether
the wall was reached. Record reviewer token usage where the harness exposes it;
otherwise record `unavailable`, never an estimate or a telemetry service.


4 — Does it go again?
=====================

**A material scope change earns a full review.** New feature work, a scope
addition, a redesign, or a conflict resolution that changes the pull request's
own behavior starts `Review the head` again and establishes a new scope. A
comment reflow, changelog line, or clean base merge does not. The classification
is content-based, so rewritten history preserves the existing scope when its
pull-request content is unchanged.


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
- **Fixes that will not converge**, at `Verify the fix delta`: three
  consecutive passes each recording defects. A report, not a question — the
  defects go on the pull request, it stays draft, and nothing waits on an
  answer.

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
