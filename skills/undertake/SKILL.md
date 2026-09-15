---
name: undertake
description: >-
  This skill should be used whenever a GitHub issue, or a task this skill is
  explicitly invoked on, is being taken from its description to a pull request
  ready for review — "/undertake", "undertake #34", "undertake adding a retry
  loop", "implement #191" — and on Claude's own move from reading an issue to
  writing code for it. It covers keeping that pull request current after it
  goes ready too: "the PR is behind master", "bring the branch up to date".
  Two things fire it: an issue handed over to be worked on, or an explicit
  invocation. An invocation carrying no issue opens one itself, but one of the
  two is still required — "implement a retry loop" and "fix this function",
  with neither, are ordinary work and must NOT fire it. Supplies the order of
  the steps, the gates between them, the ready gate a branch behind its base
  does not pass, and the base merge that keeps it current; the round is
  `review-cycle`'s. Not for reading or discussing an issue: "what does #191
  say" is a question, not an assignment.
---

# Undertake

An issue in, a pull request ready for review out, and kept current with its
base branch after that. Twelve steps, and this skill is the order they run in
— the first of them, `Open the issue`, skipped in the common case where the
work already has an issue. Where it does not, that step supplies one: an issue
is what this skill takes in, and untracked work is what running without one
leaves behind.

It is an orchestrator, in the same shape as `pr`: **it invokes, it does not
restate**. The task branch and execution root live in `task-worktree`, the
title convention in `pr-title`, the pull request itself in `pr`, the review
round in `review-cycle`, what is worth asking the user in `judgement-call`,
and the engineering standard in the constitution. Where a step below names a
rule one of those owns, it names it as a pointer and cites the owner — a rule
that acquires a second home here is one whose copy goes stale, and a citation
is what makes the drift visible. There is no exception.

What this skill owns is the sequencing and the gates between the steps.

**The routes are per harness, and they live beside this file.** Every call the
steps below need is named in words here and resolved to a route there:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi,
[`references/codex.md`](references/codex.md) for Codex. Read the one for the
harness in use before `Claim the issue`, and read `task-worktree`'s reference
for the harness before `Establish task worktree`.

**Every step has a name, and the name is how it is cited** — here and in every
other file that refers to one. The numbers order the sequence and do nothing
else: insert a step and all of them move, while a name stays where it was put.
That is why `review-cycle` names `Open the draft` and `Ready for review`
rather than the positions those two occupy today.
[`0005`](../../docs/notes/0005-steps-are-cited-by-name.md) is the decision and
`scripts/check-step-names.py` is what enforces it.


The sequence
============

| # | Step | Owner |
| - | ---- | ----- |
| 0 | `Open the issue` | this skill, `issue-deps`, `issue-labels` |
| 1 | `Title the session` | `session-title` |
| 2 | `Read the issue and its edges` | the harness's issue client, `issue-deps`, `issue-labels` |
| 3 | `Establish task worktree` | `task-worktree` |
| 4 | `Claim the issue` | this skill |
| 5 | `Implement` | the constitution |
| 6 | `Open the draft` | `pr` |
| 7 | `Review the head` | `review-cycle` |
| 8 | `Fix, answer, resolve, push` | `review-cycle` |
| 9 | `Verify the fix delta` | `review-cycle` |
| 10 | `Ready for review` | the harness's pull request client |
| 11 | `Keep it current` | this skill, `review-cycle` |

`Review the head`, `Fix, answer, resolve, push`, and `Verify the fix delta`
are `review-cycle` stages and carry the same names for that reason. `Ready for
review` is not among them — it is this skill's gate, and `review-cycle` says
what independent evidence it requires.

0 — Open the issue
------------------

Skipped where an issue is already in hand — handed over in the request, which
is the common case, whether or not this skill was named. Where there is none,
this step supplies one, and the eleven after it are unchanged: what would
otherwise happen is a branch, a review and a merge with no record of why any of
it was wanted, and a pull request body with nothing to close.

**Search before writing.** Search the repository's open issues first: work
described in a prompt has often been described in an issue already, and a
second issue for it splits the trail in two. Where one already covers the
request, that is the issue — go on to `Title the session` with it, and say
which one it is, so a wrong match is corrected before the task worktree exists.

Otherwise open one. Title and body record what
was asked and no more: an issue is the statement of the request, and scope
invented for it is scope the pull request is then measured against. No
permission is asked — the invocation is the authorisation, and an issue is
cheap to close.

**A request too vague to write an issue for is a stop.** This is the intent
gate of `Read the issue and its edges` arriving early, and the constitution's
rule against guessing at intent: an issue that guesses at what "done" means is
worse than no issue, because the guess then reads as settled.

**Every issue this step writes carries a label**, and `issue-labels` picks it.
An unlabelled issue is one nothing can sort and nothing can decide readiness
from, and the label is free to set at creation — the issue client takes the
labels on the call that opens the issue. The issue this step writes is the work in
hand, so it is a `task`, a `bug` or a `research` issue; it is never an `epic`,
which coordinates issues that already exist, and never a `proposal`, which is
the vague request this step has already refused to write.

Edges are `issue-deps`' business. Unlike the closing reference at `Open the
draft`, a parent or a blocker for a new issue is *inferred*, so it is that
skill's evidence test that decides whether one is written, and its report that
says one was.

1 — Title the session
---------------------

As soon as there is an issue, and before anything else is read of it. Read the
issue *title* — that is all this step needs — and title the session from it
before reading the body. A web session otherwise takes its name from the first
prompt it received, which is the prompt that invoked this skill.
`session-title` has the form and the budget.

`session-title` stops where its surfaces do not exist — on a laptop without
the Claude Code Remote tools, and outside it on no Omp runtime — and on the
tools alone there is no title to set. That stop is the step's, not the
sequence's: say so in a
line and go on to `Read the issue and its edges`.

2 — Read the issue and its edges
--------------------------------

The body, and then the graph: parent, sub-issues, blocked-by. Read both
through the harness's issue client, which the reference file names. **An issue
blocked by an open one is a stop, not a start** — say which issue blocks it
and wait. Reading the graph is free and needs no confirmation; `issue-deps`
says so.

**An issue too big for one pull request is `epic`'s, not this sequence's**, and
this is where that is noticed — here rather than at `Open the issue`, which is
skipped in the common case where the issue was handed over. `epic` sizes it,
decomposes it, and each task issue it opens comes back here as the issue this
sequence takes in. **An epic itself is a stop**, under `Where it stops and
waits`.

The label too, because it states whether the issue is ready for an agent at
all, and `issue-labels` says what each one means. The `epic` label is that
stop arriving as one word. **A `proposal` is a stop as well** — its shape is
still open, so decomposing it is `epic`'s work and agreeing the plan is the
user's. **Two of the five on one issue is a stop too**: the label answers the
readiness question twice, and `issue-labels` says why neither answer wins.
`task`, `bug` and `research`, one of them and no other, run through — with
one caveat on the last. **A `research` issue whose answer turns out to be a
set of issues, or a decision not to do the thing, has nothing to put on a
branch**, and that is a finished research issue rather than a failed one.
Where `Implement` reaches that conclusion, say so and stop: the answer goes
on the issue, `epic` writes the issues where there are issues to write, and
this sequence does not open a pull request with nothing in it.

**An issue carrying no label is labelled here rather than merely noted.** It
runs through — unlabelled is not blocked — and it is the only place the
standard's one-label-per-issue invariant is ever repaired: `Open the issue`
labels everything it writes and so does `epic`, so an unlabelled issue is one
a person opened. `issue-labels` picks the label and the issue client applies
it, on a write that needs no more permission than the claim a moment later.
Naming the label and moving on leaves the next session asking the same
question of the same issue.

The comments too, because `Claim the issue` needs to know whether it is claimed
already — by this session, which means the sequence is being re-entered, or by
another.

3 — Establish task worktree
---------------------------

Invoke `task-worktree`. The issue now supplies the task identity, and no
repository research has begun. That skill owns the feature branch, its base,
the sibling worktree, and every later operation's root.

The branch it establishes is the branch `Claim the issue` announces. Do not
select, create, rename, or check out a second branch here. Where a harness
already designated one branch for this task, `task-worktree` consumes it;
otherwise its own project-convention and task-name rules decide.

4 — Claim the issue
-------------------

One comment on the issue says that this session has taken the work. It goes up
after `Establish task worktree`, so the branch it names exists and is the one
the implementation will use, and before `Implement`, so another session can
see that the work has started.

After `Read the issue and its edges` rather than before it, because the edges
decide whether there is anything to claim: a blocked issue stops there, and a
claim on work that is not starting is a false record.

Beyond the claim itself the comment always carries:

- **The branch** established by `task-worktree`, **linked** as
  `[branch](https://github.com/OWNER/REPO/tree/BRANCH)`. `OWNER/REPO` is the
  repository the branch will be pushed to, which on a fork need not be the
  repository the issue is in. Read it from the harness's session call where
  that call supplies it, or from the remote `task-worktree` resolved. Built
  from the issue's repository instead, the link can point to the wrong fork.
  Until `Open the draft` nothing else on GitHub ties the issue to this branch.
  The link can return 404 until the first push; write it anyway, because the
  alternative is a branch name the reader must turn into a URL by hand.

Where the harness has a session call, the comment also carries:

- **The model that served the turn**, which is what actually ran and moves
  with a fallback that leaves the rest of the session untouched. Where the
  model the session was *set* to run disagrees with it, name that too: the gap
  between the two is the half of the record worth having. Never a name recalled
  instead of read — a provenance record that guesses is worse than one that
  says nothing. The reference file names the fields that answer both.
- **The session**, as a link built from the same call's session id. The
  identifier is what the reader needs; the link is that identifier and
  somewhere to go with it, and the reference file has its form.

The model and session come from the harness's session call, where it has one —
the call `session-title` documents. A branch designated by that call must be
the branch `task-worktree` established; disagreement is a collision, not a
choice between two branch sources.

**Where the harness supplies no session call the comment still goes up with
the branch alone.** It does not announce the unavailable metadata: omission is
the harness-neutral record. The branch comes from the task worktree's Git
state, never from a fresh naming decision in this step.

**Once per session, not once per run.** A sequence re-entered — its blocker
cleared, the issue handed over again — does not claim what it has claimed
already, and the comments read at `Read the issue and its edges` show it. A
claim from a different session is not suppressed: that collision is the thing
the claim exists to make visible, and it is worth a line to the user before
implementation begins.

5 — Implement
-------------

The constitution governs, under *While you write code*, *Before you commit* and
*When you hit a wall*. Nothing about how to write or commit the code is decided
here.

6 — Open the draft
------------------

Push the branch, then invoke `pr`: it owns the branch guard, the existing-PR
check, draft state, and the call on whether there is an issue to reference —
there is, and it is this one. The `Issues` section of the body closes it, and
`issue-deps` treats that line as the write into the graph. Its evidence test
has nothing to weigh here, because the edge is given by the assignment rather
than inferred: the issue being implemented is the issue the pull request
closes.

**The push is what runs the project's gates.** The constitution's *Before you
call it done* sends them to CI rather than to this machine, so no local gate
step comes before this one. The draft may open red, and `Review the head`
waits for the result either way. A red check is answered at `Fix, answer,
resolve, push`, and the ready gate below is what it has to satisfy in the end.

7–9 — Review the head, fix, then verify the delta
--------------------------------------------------

Invoke `review-cycle`. It owns the CI wait, full review, finding protocol, and
independent bounded verification. First record the reviewed SHA and every
finding disposition. Batch all fixes, including CI and bot fixes, push them,
and wait for CI on that head. Then run `Verify the fix delta` when the
pull-request content changed behavior, contracts, or workflow rules. It is one
pass for the batch, never one per commit or finding.

A first pass that finds defects returns to `Fix, answer, resolve, push`, then
receives exactly one final targeted confirmation after CI. A defect in that
confirmation, an unavailable reviewer, incomplete verification, or an
exhausted pass limit keeps the pull request draft and reports the blocker.
Initial execution and a resumed session read the durable review record before
acting; they do not reset the allowance for a resume, rewritten history, bot
finding, or late CI correction.

Only a material scope change runs a new `Review the head` round. A base merge
or history rewrite with unchanged pull-request content does not. `review-cycle`
owns the content comparison and rejected-finding evidence rule.

10 — Ready for review
---------------------

The harness pull-request client takes it out of draft only after `The gate`
below holds. It does not review; `review-cycle` supplies the full review and
independent verification that the gate consumes.

It does not review. Marking a draft ready is a natural moment to reach for one,
and the branch was already reviewed at `Review the head` — whether that review
is stale is `review-cycle`'s provenance test and is answered inside the round,
not here.
Where `review` is live rather than in `attic/skills/`, this is also what
discharges the leaving-draft trigger in its description: it fires on exactly
the moment this step occupies, and a round already run on this head is that
trigger already answered.

11 — Keep it current
--------------------

Commits land on the base branch while the work is written and while a
reviewer reads, and a branch behind its base was reviewed and tested against a
tree nobody will merge into. This step brings the base branch in, and it is the
only step that runs more than once.

**Its first run is before `Ready for review`, not after it.** The gate's first
condition is that step's merge, so the sequence reaches it once out of the
table's order and then again on its own cadence. Ready is not the end either,
so it runs again on the cadence under `When it looks`.

**The merge is the harness's update-branch call**, whichever one the reference
file names. It merges the base branch into the head server-side, so it needs no
checkout: by the time this
runs, the session may be on another branch, and the working tree it had may be
gone. The call is the test as well as the merge — GitHub answers that the
branch is already up to date when there is nothing to bring in, so nothing
here has to compute how far behind the branch is.

**A merge, never a rebase.** A rebase rewrites history somebody is reading,
and it voids the mark `review-cycle` recorded at `Review the head`. A merge
commit leaves both intact.

When it looks
-------------

Once before `Ready for review`, as the gate's look rather than the cadence's.
The cadence itself starts from the ready pull request, and it needs a **durable
wake** — a scheduled wake that survives the session that armed it. Where the
harness has one, the cadence is a check-in every two minutes, one scheduled
wake at a time, carrying the instruction to look again — the discipline
`review-cycle`'s `The backstop` states for the same reason. The reference file
says whether the harness in use has such a wake, and names the call.

**Where it has none, there is no cadence.** Say once, at `Ready for review`,
that the branch is kept current by the next session that picks the pull request
up, and stop. A watch a surface cannot keep is worse claimed than skipped. A
timer that dies with the session is not a durable wake, whatever it is called;
[`0011`](../../docs/notes/0011-two-harnesses-one-skill-tree.md) is the
decision, and names the harness that has one of those.

**Never end a turn with the wake slot empty while the check-ins are running.**
They run from `Ready for review` until the pull request is merged or closed or
the user says to stop, and on a surface that has the durable wake at all — the
three exits below, and nothing narrower. Inside them the slot is that one
timer, held by the identifier the call returned, and it empties two ways: the
timer fires, or a CI wait cancels it at `End the wait`. Both are the same
instruction — fill it before the turn ends. What arms a check-in is therefore
an empty slot rather than a particular kind of wake: a wake with the timer
still in flight arms nothing, and a wake that found nothing to do still leaves
a wake behind it. A turn that ends with no timer and no subscription is a
session asleep on a pull request nobody else is watching, which is the report
[`0010`](../../docs/notes/0010-the-wake-slot-is-never-empty.md) records, and
[`0011`](../../docs/notes/0011-two-harnesses-one-skill-tree.md) scopes to
Claude Code.

**Two minutes, the same interval `review-cycle` waits on CI with.** A busy
`master` takes a commit every few minutes, so a slower check-in is a branch
kept behind on purpose, and the merge itself costs a call and a CI run that
this repository answers in seconds. Behind is the state to leave as briefly as
the scheduler allows.

**The one floor is a run in flight.** A check-in that finds CI from the last
merge still going does nothing: merging again restarts the run it is waiting
on. Where CI answers in seconds that floor almost never bites, and where it
answers in twenty minutes it is what keeps the branch from never being green.

A merge-conflict notice does not wait for the cadence either. It is the case
where behind has already cost something, and it is answered on the wake that
reports it.

The check-ins end when the pull request is merged or closed, or when the user
says to stop. A pull request nobody merges is not a reason to wake a session
for ever.


After the merge
---------------

The head moved, so CI runs again. Wait for it the way `review-cycle`'s
`How to wait` says, and answer a red check under `Fix, answer, resolve, push`.
That wait borrows the wake slot for its backstop and gives it back at
`End the wait`: the check-ins above are armed again before that turn ends,
whichever way the wait ended, and after the round the wait was clearing the way
for rather than into it.
**Red CI is how a base merge reports that it broke something**: the base
changed what the branch depends on, the branch's own diff is untouched, and no
review of that diff would have found it.

**A clean merge does not earn a round.** `review-cycle`'s `Does it go again?`
classifies it under `Neither`, and the reason is what the round's review reads —
the pull request's three-dot diff, which after a clean merge is byte-identical
to what `Review the head` already reviewed. A base branch that moves daily
would otherwise buy a review a day for a diff nobody changed.

**A conflict resolution does.** Resolving a conflict rewrites the branch's own
files, which is `Changing what the code does` in that same classification.
One round over it, and `review-cycle` decides anything further.

A round after ready goes back to draft
--------------------------------------

**Return the pull request to draft** before `Review the head` runs, and ready again through `The gate` below when the round closes — the
same gate, not a second one. A pull request under review is not ready for
review, and a reviewer must not be reading a branch that is changing
underneath them.


The gate
========

The hand-typed prompt this skill replaces got three things wrong. Two of them
were about the round rather than the sequence and left with it — `review-cycle`
carries *review once per diff* and *a reviewer, not a subagent*. The third is
this skill's, and it is the one `Ready for review` turns on.

Ready is a gate, not a step
---------------------------

"After fixing, set the PR to ready" reads as unconditional. It is not. The
pull request goes to ready only when **all** of these hold:

- The branch is current with its base branch and merges cleanly. `Keep it
  current` owns the merge that makes this true, and it is tested first because
  the merge moves the head: every condition below is about the head a reviewer
  will actually read, and a merge run after them would leave them answered
  about a commit nobody sees. A conflict is that step's stop, arriving early.
- CI is green on the head commit. **Pending is not green** — wait for it the
  way `review-cycle`'s `How to wait` says, rather than treating an unreported
  check as either answer. The mechanism has one home, and it is not this one.
- No review thread is unanswered or unresolved — from any reviewer, not only
  from the round at `Review the head`.
- Every finding that round raised has been fixed, or rejected with a reason on
  its thread, or deferred with the user's agreement.
- The independent verification record for the scope is clear on the current
  behavioral head. The only valid second pass is the clear final confirmation
  after defects from the first; unavailable or incomplete verification, a
  final-pass defect, or a cap hit is not approval.

A branch behind its base, red CI, or an open thread means it **stays a
draft**, and the reason is stated in one line. A red pull request marked ready
is a claim about the work that is not true, and so is a ready one that does not
merge.

The gate is also what a round at `Keep it current` returns through. That round
sends the pull request back to draft, and these five conditions are what let
it out again — the same five, tested again, rather than a second gate written
for the second round.


Where it stops and waits
========================

Autonomy is the point, so each pause has to earn itself. Ten stop the
sequence. Seven stop it to *ask* — the ambiguous issue, the request too vague
to write one for, an issue labelled `proposal`, an issue carrying two of the
five labels, the failing approach, a designated branch the harness states
ambiguously, and a base merge whose conflict is a real one. A blocked issue, an
epic, and a running check stop it to report, and wait on something other than
an answer.

- **A blocked issue, an issue whose intent is genuinely ambiguous, or a
  request too vague to write an issue for.** The constitution forbids guessing
  at intent; this is that rule, at `Open the issue` and at `Read the issue and
  its edges`.
- **An epic**, at `Read the issue and its edges`. An epic carries no code, so
  there is no branch to cut and no pull request to open. Say which issue is the
  epic, name the tasks that are ready, and undertake one of those — `epic` owns
  the stop and the wording, and the `epic` label is what says so in one word.
- **An issue whose label does not clear it for work**, at `Read the issue and
  its edges`. A `proposal`'s shape is not yet decided, so deciding it is the
  user's and decomposing it is `epic`'s; an issue carrying two of the five
  answers the readiness question twice and answers it neither way.
  `issue-labels` is what each label claims, and what a contradiction between
  two of them costs.
- **More than one designated branch** for this repository, at `Cut the
  branch`'s first source. Guessing which one the harness will accept risks a
  claim already posted at `Claim the issue` that no push can honour.
- **The approach failing mid-implementation** — the constitution's *When you
  hit a wall*, at `Implement`. A pull request that documents a wrong turn is
  worse than no pull request.
- **CI still running**, at `Ready for review`. A wait, not a question —
  nothing is asked, and nothing proceeds on a check that has not reported.
- **A base merge that conflicts**, at `Keep it current`.
  The update-branch call cannot resolve a conflict: it fails
  and changes nothing, so a resolution is a local merge, resolved and pushed.
  Resolve it where the resolution is plain — a moved import, two files that
  never met. Where both sides changed the same logic, picking either loses
  behaviour, and that is the constitution's rule against guessing at intent:
  name the conflicting files and wait.

The round at `Review the head` and `Fix, answer, resolve, push` has two stops
of its own — its own wait on CI, and a review finding whose fix is a real
trade-off. Both are `review-cycle`'s, and the second is `judgement-call`'s gate
applied inside it.

Everything else runs through. No permission is asked to open the issue, to
claim it, to commit, to push, or to open the draft.


Non-goals
=========

- **Does not merge the pull request.** `Keep it current` merges the base
  branch *into* the pull request and never the other way. Landing it is
  somebody else's.
- **Does not close the issue by hand.** The pull request body does that, and
  the merge does it.
- **Does not fire on reading an issue.** Discussing #191 is not undertaking
  it. "What does #191 say", "summarise #191", "is #191 still relevant" are
  questions; answer them, and do not cut a branch.
- **Does not undertake an epic.** An epic carries no code, so there is no
  branch to cut and no pull request to open. `epic` owns that stop, and says
  to undertake one of the epic's ready tasks instead.
- **Does not fire on work it was not asked to undertake.** "Implement a retry
  loop", with neither an issue nor an invocation, is ordinary work, and running
  twelve steps and a review round over it would be the heaviest possible way to
  write ten lines. `Open the issue` makes the issue reference optional; it
  does not make it the only thing that was ever doing the separating. An issue
  handed over, or this skill named — either fires it, and neither is ordinary
  work.
- **Does not open an issue for anything but the work in hand.** `Open the
  issue` tracks what was asked for. A bug noticed in passing is worth reporting
  to the user; it is not this run's second issue.
- **Does not review, and does not answer a review.** The round is
  `review-cycle`'s, and it is reachable without this sequence: a pull request
  opened by hand, or one a reviewer has come back to, gets the same round
  without an issue anywhere near it.
