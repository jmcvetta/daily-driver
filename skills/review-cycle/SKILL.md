---
name: review-cycle
description: >-
  Use for `/review-cycle` whenever a pull request is reviewed, alone or then
  answered, its threads replied to or resolved, or its checks awaited. Supplies
  the CI wait on the pushed head, the review invocation and level, a durable
  review record, the finding response protocol, bounded independent fix-delta
  verification, and the test for whether a later push changes the full-review
  scope. Not for opening or updating a pull request (`pr`) or marking a draft
  ready, which is the caller's gate.
---

# Review cycle

One full review per scope, then an independent fix-delta pass for every batch
of corrections pushed under it, until one comes back clean or three in a row
do not. Every finding is answered, and a behavioral fix is verified without
repeatedly auditing unchanged pull-request content. A standalone review records its
findings and stops; it does not turn into an implementation run.

The analysis uses the active harness route's default review surface unless the
operator explicitly selects another independent review method. This skill does
not supply the analysis. What it supplies is the six things around it — the
wait for CI, the level, the durable review record, the thread protocol, bounded
fix verification, and the full-review test — none of which any review surface
has an opinion about.

**The routes are per harness, and they live beside this file.** Every operation
below is named in words here and resolved to a call there:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi,
[`references/codex.md`](references/codex.md) for Codex. Read the one for the
harness in use, and read it before the wait rather than during it — the wait is
where the harnesses differ most, and one of them cannot wait at all.

`pr` starts and owns ongoing base maintenance for agent-opened pull requests;
its `Keep it current` watch remains active through review rounds. `undertake`
invokes that maintenance and owns whether its pull request goes ready —
including the return to draft while a later round runs. This skill borrows the
watch's CI wake but owns neither base maintenance nor readiness. Nothing here
marks a draft ready or merges anything.

For a specification-backed task, review the implementation against both the
task's allocation and exclusions and the referenced requirement IDs in the
document at its exact recorded commit. Check the delivered revision and
evidence in the PR body. A changed governing specification or mismatched
allocation is a finding routed to `epic`, not implicit approval to change
the contract or amend the specification in an implementation PR.


The round
=========

| # | Stage | Owner |
| - | ----- | ----- |
| 1 | `Review the head` | an independent reviewer |
| 2 | `Fix, answer, resolve, push` | this skill |
| 3 | `Verify the fix delta` | an independent reviewer |
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

**A standalone review ends after `Review the head`.** It reads the relevant
history, reviews the requested pull request, records its result durably, and
reports it. It does not enter `Fix, answer, resolve, push`, resolve its new
threads, alter draft state, or merge. A request to fix or answer existing
findings is not standalone and follows the relevant later stage.


1 — Review the head
===================

**Review a stable pushed head without waiting for CI.** Queued or running
checks are not passing checks, but do not prevent independent review. Review
and CI may proceed concurrently. Bind review evidence to the reviewed SHA;
if the head changes, apply the review-scope and fix-delta rules below. An
observed CI failure goes to `Fix, answer, resolve, push`. Current-head green
CI remains required by the caller's readiness gate.

Reuse an existing review or CI watch for the same head rather than starting
duplicates. An unavailable CI wait does not prevent review.

First **read the relevant review record**, then use an independent human or
agent review of the pull request. Existing credible review can satisfy this
stage when it covers the relevant current content; do not repeat it merely
because it used a different account, method, or GitHub review event. The
reference file names the default invocation and recording routes.

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
- **A harness may observe a third source: workflow runs.** A workflow can be
  queued or running before it registers a single check, so checks and statuses
  alone can show a passing subset while CI is unfinished. Where the reference
  names a workflow-run read, a run for the head that is not terminal blocks the
  verdict, and a read that cannot establish what has registered is an incomplete
  observation, not a pass. The calls are the reference's.
- **An empty inventory is unknown until absence is established.** A newly
  pushed head may still register checks. Establish a no-applicable-CI result
  only from complete, current repository workflow configuration, applicable
  required-check context (including branch rules and rulesets), and the
  event, base, head and changed paths that select workflows for this change.
  Account for other configured check providers too. If any applicable check
  may still register, keep the result pending; a known missing required check
  is never a pass. Denied, malformed, truncated or failed reads leave absence
  unknown. Record the evidence and conclusion as **no applicable CI**, not
  as checks passed. Reassess it when the head or relevant configuration changes.
  A partial watch that cannot establish absence or wake itself reports its
  continuation limit rather than hiding an unbounded poll.
- **A wake that is not about a check is still just a read.** The round is its
  own loudest source of the other kind: a review that posts a thread per
  finding, and a reply to every one. None of that is a check reporting, so none
  of it moves the wait — read, find nothing changed, and go on with what the
  turn was doing. A wake arriving after the wait is over is a no-op for the
  same reason.
- **Bound each observation window to fifteen minutes, not task ownership.**
  On expiration, read the head and CI again. If work is still nonterminal,
  renew the bounded observation through the harness's supported continuation.
  Do not mark it human-blocked or require another user prompt merely because
  a window ended. Review may proceed while CI remains pending.
  Report changed conditions, not repeated timeout notices. Diagnose a genuine
  observation failure; report an unsupported continuation under the rule below.

**Never a `sleep`, in the foreground or in the background.** A sleep is a
timer, not a test of the thing waited on — it expires while the checks are
still queued as readily as it expires long after they went green. Backgrounded,
it is also the failure this mechanism was written for: a job named *"Wait ~3
minutes for CI"* that sits until it times out and never brings the session back
to the loop.

**No unmanaged shell wait where the session is unattended**, regardless of
which command-line clients are installed. A foreground watch is bounded by
the Bash tool's own timeout, and a backgrounded shell job is not supervised
as a process the session can inspect and stop. Use the harness's supervised
process service when its reference documents one; a service is not an
unmanaged shell job. `sleep` remains forbidden as a substitute for observing
CI.
[`0006`](../../docs/notes/0006-waiting-for-ci.md) records the original
decision; this rule clarifies the supervised-service boundary.

**A surface that can neither block nor wake itself cannot wait.** Read the
checks once; if they have not all reported, report the continuation limit.
Review can still proceed, but readiness must wait for current-head green CI.
The harness reference identifies whether this limit applies.


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

**Independent review needs a bounded scope and a durable result.** A suitable
human or agent reviewer inspects the relevant changes for concrete defects and
unmet requirements. The author cannot substitute self-review. Give an invoked
reviewer the requirements, reviewed revision, relevant prior findings and
dispositions, and a route for recording the result on the pull request.

**Use the active harness route's default review surface unless the operator
explicitly selects another independent review method.** Honor that selection
for its stated scope, including a requested switch away from a running review;
stop the superseded invocation before starting its replacement. Do not silently
fall back or change persistent reviewer configuration. Keep the selected
method and scope clear in the review evidence. An operator-selected method
still needs independent analysis of the relevant content and durable findings;
selection alone is not a completed review. If the method is unavailable or
its coverage is incomplete, report the precise gap. The harness reference
supplies its default invocation and the bounded brief for `Verify the fix
delta`. A missing alternative-specific example is not itself evidence that
the selected method is unavailable.

**Read enough history to preserve decisions and avoid duplicate findings.**
Use the last known review state, new reviews and replies, open findings, and
prior decisions relevant to the delta. Pass that context to the reviewer,
not just the author's verdict. Retain a concise checkpoint or links so the next
round can read incrementally. Reconstruct the full history, including resolved
and outdated threads and their replies, on resume without reliable state, a
dispute, or a gap in that context. Paginate each needed query to completion.

**Keep actionable findings durable and easy to answer.** Prefer inline
threads for line-specific defects when valid diff anchors are available.
Anchor them to the reviewed commit, path, side, and valid line or range.
Use a suggestion block only when it clarifies the replacement; it never
replaces the explanation of the defect. Put cross-cutting or unanchorable
findings in a review summary or pull-request comment; never invent an anchor.
A clean review needs a concise durable result too. No particular account,
GitHub review event, or comment format is required.

**Use native publication where available; otherwise record the returned
result through the available GitHub route.** Link existing human or agent
review rather than republishing it. Check the relevant existing record and
returned identifiers or links before posting, so a resumed run does not
duplicate findings. A local reviewer result must not remain only in the
author's transcript when a pull request is available.

**Check freshness and anchors immediately before publication.** Keep the
reviewed revision attached to its result; never attribute it to content the
reviewer did not inspect. If the head moved, compare the relevant content.
Unchanged content can retain the evidence; behavioral changes require the
applicable new review. Revalidate inline anchors, or preserve the findings in
a summary with clear file and code references when inline publication cannot
be used.

**Report incomplete recording, never claim it succeeded.** If no durable
GitHub route works, retain the findings and state the publication failure.
An invalid inline anchor alone need not prevent a durable summary.

**One finding has one conversation.** A repeated finding links to the earlier
thread and disposition rather than reopening the argument. A recommendation
that reverses a recorded decision names the decision and its new evidence or
changed constraint. A prior decision is evidence, not immunity from a
demonstrated defect.

**A local review with no pull request still returns its findings and says that
GitHub recording is unavailable.** It does not create a pull request to obtain
a record.

**Keep enough evidence to establish coverage and follow findings.** A review
or linked pull-request comment identifies the reviewed revision or content,
scope, independent source, result, and any findings. Replies or linked
follow-up records preserve substantive dispositions. This is evidence, not
a required field set or a separate ledger. Existing credible records need
not be rewritten. Published artifacts follow ordinary `provenance`; missing
historical attribution is not a new review gate.


2 — Fix, answer, resolve, push
==============================

Every substantive finding gets a durable disposition. Reply on its thread
when it has one, and close the thread after answering:

1. **Implemented** — fix it, record the fix, and resolve any thread.
2. **Rejected** — record the reason, and resolve any thread. A rejection is
   an answer; only silence is not.
3. **Deferred** — only where the user asks for it. The agent does not propose a
   deferral: `judgement-call` names "leave a TODO" as the option that is never
   a real one, so a deferral the agent offers is the noise that skill deletes.
   When the user does defer, record what was deferred and to where, then
   resolve any thread — an open thread would claim the question is still live.
4. **A repeat finding** — a reviewer opening a new thread for something already
   rejected in an earlier round — is resolved with the same message as before.
   A fresh variation invites a fresh argument over a question that was already
   answered. This one is live precisely because `Review the head` can run again
   and re-raise what this stage rejected.
5. **Never left open silently.** The rule the other four exist to serve.


Every reviewer uses this protocol — the agent's own findings, a human's, a
bot's, or locally returned output. For findings recorded in a summary or
comment rather than threads, record each disposition there or in a linked
follow-up. No substantive finding may disappear in a transcript-only exchange.

The reply
---------

Verdict-first, concise, technical. A reader skimming twenty threads should
never have to parse a paragraph to learn whether the finding was implemented or
rejected. No thanks, no apologies, no restating the finding, and no poetry in
an actionable reply. The active route supplies `provenance` for every
body-bearing write, including individual finding replies. On Omp, the wrapper
appends and deduplicates the block on each review and reply;
do not format it in those bodies. Other routes follow `provenance`'s block rules.

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

**Verify a behavioral delta independently after the batch is pushed.** The
verification may overlap CI on that head. Passing CI does not replace this pass.
A red result does not approve the head or satisfy the caller's readiness gate.

Give one independent human or agent reviewer the prior reviewed revision,
current revision, relevant original findings, and recorded dispositions.
It verifies that implemented fixes solve their findings and do not regress
affected behavior. It may read surrounding code and affected callers. It must
not restart a full pull-request audit, solicit style work, or accept the
author's verdict as verification. The harness route names a concrete invocation;
existing independent review that covers this delta can also supply the result.

Classify the pull-request content delta, not commit provenance. A change to
behavior, a contract, or a workflow rule requires a pass, including Markdown
that changes workflow behavior and fixes prompted by CI or bots. Pure formatting
does not. A clean base merge whose three-dot pull-request content is unchanged
does not. Mixed changes require a pass. This content comparison also applies
after a rebase, amend, or squash: a missing ancestor is never evidence of no
change.

**Every behavioral fix batch needs the pass that confirms it.** Do not refuse
verification of a pushed fix because an arbitrary pass budget was spent.
The bound below counts fixes that do not converge, not passes as such.

**The loop ends on the first clean pass.** A pass that records concrete
defects earns one batched correction, pushed, and one more targeted pass over
that correction delta and its regression risk. CI runs independently; observed
failures enter the correction path. Repeat while passes keep finding defects.

**Three consecutive passes that each record defects is the wall**, in the
sense `undertake`'s operational escalation policy gives it: the corrections are
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

Record a concise result on the pull request, or link an existing independent
result: what revision or content and fixes were checked, whether they passed,
and any remaining defects or coverage limits. Preserve enough prior results
to recognize three consecutive defect-producing passes without a fixed
verification template, empty fields, wall-state token, usage record, or
reviewer-transcript inspection.



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

- **CI still running** does not block review. At readiness it remains a wait,
  not a pass; `How to wait` preserves supported continuation.
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
