---
name: undertake
description: >-
  This skill should be used whenever a GitHub issue, or a task this skill is
  explicitly invoked on, is being taken from its description to a completed
  result — a pull request ready for review or an evidenced answer-only research
  result — and on the agent's own move from reading an issue to writing code
  for it. It covers keeping a pull request current after it goes ready too:
  "the PR is behind master", "bring the branch up to date". Two things fire
  it: an issue handed over to be worked, or an explicit invocation. An
  invocation carrying no issue opens one itself, but one of the two is still
  required — "implement a retry loop" and "fix this function", with neither,
  are ordinary work and must NOT fire it. Supplies the step order and gates,
  the ready gate a branch behind its base does not pass, the pause on a human
  action, and the base merge that keeps it current; the round is
  `review-cycle`'s. Not for reading or discussing an issue: "what does #191
  say" is a question, not an assignment.
---

# Undertake

An issue in, an evidenced result out — a pull request ready for review for
repository changes, or a completed answer recorded on the issue for
answer-only research — and any pull request kept current with its base.
Twelve steps, and this skill is the order they run in. `Open the issue` is
skipped in the common case where the work already has an issue. Where it does
not, that step supplies one: an issue is what this skill takes in, and
untracked work is what running without one leaves behind.

It is an orchestrator, in the same shape as `pr`: **it invokes, it does not
restate**. The task branch and execution root live in `task-worktree`, the
title convention in `pr-title`, the pull request itself in `pr`, the review
round in `review-cycle`, the model, harness and session record every write
carries in `provenance`, what is worth asking the user in `judgement-call`,
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
| 11 | `Keep it current` | `pr`, `review-cycle` |

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

Otherwise open one, and author it through `issue`: the read-before-write
rule, the body contract and the label are that sequence's, invoked rather
than restated here. What stays here is the intent gate and the label rule
below — and the order: **writing the issue must not start the
implementation it describes.** The sequence continues when the issue is
written, not while the work is begun. An issue is the statement of the
request, and scope invented for it is scope the pull request is then
measured against. No permission is asked — the invocation is the
authorisation, and an issue is cheap to close.

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

`session-title` stops where its applicable reference names no title surface.
That stop is the step's, not the sequence's: say so in a line and go on to
`Read the issue and its edges`.

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

The label too, because it states the kind's agent eligibility, and
`issue-labels` says what each one means. The `epic` label is that stop arriving
as one word. **A `proposal` is a stop as well** — its shape is still open, so
decomposing it is `epic`'s work and agreeing the plan is the user's. **A
`human` is a stop as well** — there is no agent execution route for the reserved
action. **Two of the six on one issue is a stop too**: the label answers the
readiness question twice. `task`, `bug` and `research`, one of them and no
other, are eligible to proceed, subject to their body readiness tests.

**Eligibility is not body sufficiency.** Before claiming or starting work,
apply `issue-body`'s readiness test for the effective kind. Repair only gaps
answerable from the repository and preserve valid content; ask about unresolved
intent or unavailable prerequisites. Do not silently relabel an underspecified
bug or research issue `human`. A task must still pass its stricter settled-
intent and model-class checks. A research issue may finish with an answer,
follow-on issue specifications, or a supported no; do not open an empty PR
when its agreed deliverable is answer-only. Bounded inconclusive research is
complete only with the evidence, limitation, and resolution path required by
`issue-body`; failed access or abandoned work is not completion.

**Only a `task` carries a required model class.** Validate its one
`## Model class` section and rationale through `issue-body` before the claim,
repairing an old or invalid body to the current contract where the handoff is
otherwise grounded. `bug` and routine `research` use their kind-specific
readiness tests, not task class metadata. A research assignment using
`frontier` follows `issue-body`'s narrow exception: it keeps the `research`
label and must carry its single class section, rationale, explicit approval,
and exact work envelope before claim or substantive work. Do not impose the
task template on it. The class states the capability a dispatcher such as
`embark` selects a route for.

A frontier assignment must carry explicit approval and its exact work envelope
before execution. Frontier implementation also needs an explicit user
exception recorded for that implementation scope.

**Route classed undertaking work before the worktree or claim.** Resolve the
issue's exact class through the harness route, including the effective model,
effort, and all visible fallbacks. Keep the current model family, provider,
backend, and authentication route. An eligible account may refresh or rotate;
do not change shared roles or credentials to make a route available. This
policy covers undertaking workers, delegated issue work, and their execution
fallbacks. Independently configured `reviewer`, `scout`, `security-reviewer`,
and `seance` helpers are not issue implementation workers.

Prefer a supported in-session switch. Continue only when the harness confirms
the selected execution identity, not merely when it accepts a switch. While
confirmation is pending, do not establish a worktree, claim, or implement.
If an in-session switch is unavailable, a full handoff is allowed only on a
surface that can constrain and verify the same route. The receiving session
owns the whole undertaking, including its worktree and claim. The sender stops:
it must not recursively hand off, claim again, or supervise a duplicate.
If neither route can enforce the invariant, stop before the worktree or claim
and report the precise configuration or unsupported-surface gap.

In Omp, an attempt to select another issue does not replace the existing
undertaking owner. Finish the completed undertaking or resume the existing one
before selecting a different issue; use the Omp reference for the finish call.

An effective Astra/Fable route is frontier even through a lower-class role or
fallback. Ordinary classes cannot fall back to frontier. Frontier execution
requires the recorded approval and exact envelope; frontier implementation
also requires the explicit user exception above. Concrete `Model:` lines in
claim provenance record the observed model, not task metadata.

**An issue carrying no label is labelled here rather than merely noted.** It
runs through — unlabelled is not blocked. `issue` repairs an unlabelled
issue in passing too; what is special here is that nothing unlabelled gets
past this sequence: `Open the issue` labels everything it writes and so
does `epic`, so an unlabelled issue is one a person opened. `issue-labels`
picks the label and the issue client applies
it, on a write that needs no more permission than the claim a moment later.
Naming the label and moving on leaves the next session asking the same
question of the same issue.

The comments too, and they are read as content rather than as a checkbox. A
comment may carry a correction to the body, a constraint a session that came
before discovered, a decision the user made in the thread, or the record of an
attempt that failed. That material is often the most current thing on the
issue, so read it the way the body is read. **Where a comment contradicts the
body, the body is not automatically right**: report the discrepancy rather
than resolve it silently. `issue-body`'s update rule says a stale handoff is
reported rather than followed, and this is the same rule at the reading end.

A comment can also carry a stop the body does not, and this step already stops
on what it reads — a blocking edge, an `epic` label, a `proposal`. One in a
comment is the same stop.

The claim is the second reason, and it stays: `Claim the issue` needs to know
whether the issue is claimed already — by this session, which means the
sequence is being re-entered, or by another.

**The issue's own record is the first source of the task's identity.** Look for
a task branch another session already began, in this order, and take the first
source that names one:

1. An open pull request linked to the issue — one the issue read reports as
   set to close it, or a pull request whose body references the issue. Its
   head branch.
2. The `Branch:` line of a `stand-down` handoff comment.
3. The branch in the latest claim comment, only when it contains an actual
   branch link — `Branch: none` declares no resume branch. A resume branch
   applies only where the user handed the issue over to continue it. Without
   that, a claim from another session is `Claim the issue`'s collision, not a
   resume.

One branch found is the **resume branch**, and the pull request it carries, if
any, is the one to adopt. More than one distinct branch is a stop: report them
and ask. A pull request from a fork the session cannot push to is a stop too:
report it. Where no resume branch exists, `Establish task worktree` selects
the read-only route for answer-only research or invokes `task-worktree` for
repository work.

3 — Establish task worktree
---------------------------

When the agreed deliverable is answer-only research, no resume branch or
existing pull request exists, and no repository artifact is needed, this is
repository-read-only. Do not invoke `task-worktree`, create a branch, or change
repository content; continue from the current checkout.

Otherwise invoke `task-worktree`. The issue now supplies the task identity, and
no repository research has begun. That skill owns the feature branch, its base,
the sibling worktree, and every later operation's root.

`task-worktree` establishes the remote push branch and, only where its harness
route permits, a separate local execution branch. `Claim the issue` names both
identities. Do not select, create, rename, or check out another branch here.
Where `Read the issue and its edges` found a resume branch, hand that recorded
remote branch to `task-worktree`: it is fetched and attached, never recreated
from the base, and it outranks the harness's designation. Otherwise, the
harness route decides whether its designated branch is also the execution
branch.

4 — Claim the issue
-------------------

One comment on the issue says that this session has taken the work. It goes up
after branch selection: after `Establish task worktree` for repository work,
or after selecting the read-only route for answer-only research. It goes up
before `Implement`, so another session can see that the work has started.

After `Read the issue and its edges` rather than before it, because the edges
decide whether there is anything to claim: a blocked issue stops there, and a
claim on work that is not starting is a false record.

**Before posting the claim, verify the session title where the harness exposes it.** Use the issue number and title with `session-title`'s shortening rules. If the title step was missed or the current title is wrong, set it now; do not post the claim first. Leave an already-correct title unchanged. If the harness has no available title surface, report that limitation and continue without inventing another route, as `Title the session` requires. The harness denies the claim until the title is set, as `session-title`'s `When to set it` says.

Beyond the claim itself the comment always carries:

- **The work identity.** For repository work, name the remote push branch
  established by `task-worktree`, linked as
  `[branch](https://github.com/OWNER/REPO/tree/BRANCH)`. `OWNER/REPO` is the
  repository the branch will be pushed to, which on a fork need not be the
  repository the issue is in. Read it from the harness's session call where
  that call supplies it, or from the remote `task-worktree` resolved. Built
  from the issue's repository instead, the link can point to the wrong fork.
  Until the first push or `Open the draft`, nothing else on GitHub ties the
  claim to this branch. The link can return 404 until that push; write it
  anyway, because the alternative is a branch name the reader must turn into
  a URL by hand.

  For branch-free answer-only research, use `Branch: none — answer-only
  research (no repository changes)`. This is not a branch link or permission
  to create or publish a branch.

  Where `task-worktree` established separate identities, add `Local execution
  branch: <name>` as a separate line. Never link the local-only execution
  branch as the branch GitHub will carry. Ordinary and resume paths have one
  branch identity, so the linked and local branch are the same.

- **`provenance`'s block**, immediately after the work identity lines:
  the model that served the turn, the harness and its version, and the session
  reading each field — never a name recalled instead of read, and where the
  model the session was *set* to run disagrees with the one that served, both
  are named. The `Model:` and lowercase `session:` line shapes are what the
  claim lookup below and `The milestone` match on, so they are never varied
  here.
- **A brief poem, in the claiming agent's own style, placed last** — after
  the work identity, model and session, so that a reader looking for them
  finds them in a fixed place and is never made to read past verse to reach
  them. Each line is written in italics — wrapped in asterisks, line by line,
  as `HAIKU.md` at the repo root shows — because italics designate the verse
  as poetry, so a reader never mistakes a line of it for part of the claim
  data: the work identity, model or session. The style is the agent's own,
  and deliberately so: a pull request's salutation is classical and a task
  issue's opening verse is a haiku, but a claim is the agent's voice at the
  moment it takes the work.

The model and session come from the harness's session call, where it has one —
the call `session-title` documents. In branch-free answer-only research, no
branch is designated or established. Otherwise, without a resume or a
verified primary-held designation exception, a branch designated by that call
must be the branch `task-worktree` established; disagreement is a collision,
not a choice between two branch sources. With a resume, the remote push branch
is the adopted branch and outranks the designation. In the exception, the
local execution branch may differ from the designation only as
`task-worktree` verified; the designated branch remains the push/PR head.
Other paths retain one branch identity.

**The comment never goes up with the work identity alone.** For repository
work, the branch comes from the task worktree's Git state, never from a fresh
naming decision in this step. For branch-free research, the identity is
explicitly `Branch: none`; the model and session lines follow the rules above
whatever the harness supplies.

**Once per session, not once per run.** A sequence re-entered — its blocker
cleared, the issue handed over again — does not claim what it has claimed
already, and the comments read at `Read the issue and its edges` show it. A
claim from a different session is not suppressed: that collision is the thing
the claim exists to make visible, and it is worth a line to the user before
implementation begins.

**A prior claim is a resume, not a collision, in two cases:** a `stand-down`
handoff names the branch, or the user handed the issue over to continue it.
Otherwise a prior claim from another session stays a collision, reported as
above. On a resume this session still posts its own claim, naming the adopted
branch or the branch-free research route; the earliest-claim rule below
already keeps the clock start, so no new timing rule is needed. A re-entry by
the same session posts nothing, as before.

**The claim's timestamp is the undertaking's clock start.** The comment's own
`created_at` is what `The milestone` reads back when the pull request first
passes the ready-for-review gate — through resumes and later draft states. No
timestamp is written into the claim for the milestone's sake: the durable
start is the post, not a line in it. Where more than one comment carries the
claim's shape — the collision the policy above permits — the earliest of them
is the start: a later claim does not restart a clock already running. A claim
that was never posted leaves the milestone with no start to read, and `The
milestone` reports the timing as unavailable rather than guessing at one.

5 — Implement
-------------

**The session running this sequence writes the code itself** once its effective
route is confirmed non-frontier, or when the user explicitly authorizes the
bounded frontier implementation exception. No implementor dispatch is used for
ordinary undertakings.

**A direct request authorizes its scoped work and normal verification.** This
includes focused behavioral evaluation through the configured subscription.
Do not ask the user to authorize that work again merely because verification
uses inference or subscription allowance. A focused smoke is not a broad
evaluation campaign or separately metered spend. Check applicable user
authorization before declaring an approval gap.

Actual higher-priority restrictions, explicit scope exclusions, production
and dangerous-operation prohibitions, and required frontier approval still
apply. Ask only for authorization that is actually missing, including fresh
or narrower approval when an applicable instruction specifically requires it.
The request does not authorize unrelated spend or scope expansion.

**Start with the smallest proof that can invalidate the route.** Before
investing in implementation that depends on an uncertain integration, identify
and exercise the actual relevant integration and authentication path. Startup
or health checks alone do not count. Use the smallest safe local proof that
answers the question; it may be the first action in this task, not a separate
research issue by default. Record observed evidence before dependent work.
When a required input or capability is unavailable, state exactly what is
missing and continue unrelated safe work. Never report a promised test as a
completed proof.

**For deployment work, settle continuity before provisioning.** Before the
first paid provisioning or sensitive provider-returned state commit, establish
the authoritative state and configuration locations, protection for sensitive
state, recovery needs, and how another session can resume. Preserve artifact
identity and reusable nonsecret inputs without copying broad credential
stores. Include the approved host lifecycle in acceptance; session shutdown
does not itself authorize teardown. Reuse supported state/security tools and
honor all production, destructive-operation, spending, and approval limits.
Do not prescribe encrypted Git state universally or add an unapproved platform.

**Keep the agreed first useful outcome visible.** An independent improvement
does not become a prerequisite just because it is requested later. Explain
when added scope moves the first delivery; preserve every explicit acceptance
criterion. Use `judgement-call` only for an unresolved scope decision. An
informed explicit choice stands, and does not automatically open a follow-up
issue.

**Issue-only research completion.** Use this route only when the agreed
deliverable is an answer or follow-on issue specifications, no repository
changes are needed, and no pull request exists. Otherwise use the normal PR
route for the existing changes. Keep repository content read-only; never
create or publish a branch. If a resume branch exists, `task-worktree` adopts
it as usual, but this route leaves it unchanged. If no resume branch exists,
this route skips `task-worktree` and stays in the current checkout.

Gather the evidence and prepare the agreed answer. If follow-on issue
specifications are required, create those through `issue` or `epic` under
their existing gates and include their links in the result. If a required
issue cannot be created, leave the research issue open and report the failure.
Post the complete findings to the issue with `provenance`'s block. If that
write fails, leave the issue open. Close the research issue as completed only
when `issue-body`'s completion test holds and the answer was recorded. A
supported no is a result. Inconclusive work is complete only under
`issue-body`'s bounded-report rule. Failed access, unresolved blocking intent,
or abandoned work stays open and follows `Where it stops and waits`.

After completion, finish the Omp undertaking through its harness route before
reusing the session for another issue. Do not finish a stopped or incomplete
undertaking.

This route skips `Open the draft`, `Review the head`, `Fix, answer, resolve,
push`, `Verify the fix delta`, `Ready for review`, and `Keep it current`.
Never create an empty PR or mark an incomplete result complete. Repository
notes, code, or other repository artifacts use the normal task-worktree and PR
route, even when research produced the recommendation.

**A frontier session is the narrow exception.** For ordinary work it hands off
the full undertaking to an eligible non-frontier session before creating a
branch or claim, unless a supported model switch changes the verified
execution identity to a non-frontier route. It does not implement or supervise
that work on frontier. The receiving session runs this sequence and owns the
branch and claim. This is routing, not parallelism across issues; `embark` still
owns wave dispatch.

**The review round has its own dispatch.** `review-cycle`'s `Verify the fix
delta` sends a briefed subagent because the author of a delta cannot be an
independent reader.

**Parallelism across issues is `embark`'s.** Where several task issues are
worked at once, that skill opens a session or a subagent per task, and each of
them runs this sequence in its own context. Delegation there is what buys the
parallelism; delegation here duplicates a session that is already on the work.

The constitution governs, under *While you write code*, *Before you commit* and
*When you hit a wall*. Nothing about how to write or commit the code is decided
here.

**Architecture documentation is part of implementation.** Before changing the
system, read its relevant architecture documentation and diagrams. As the
implementation develops, keep affected documentation current on this branch
and in this pull request, including changes made during review or after
integrating the base branch. Describe the system as implemented now, not an
epic's promised future state. Update affected component responsibilities,
interfaces, relationships and important flows, keeping prose and diagrams
consistent; correct stale descriptions in the affected area and add the
architectural explanations needed to understand the change. Do not audit or
clean up unrelated areas. When the architecture is unchanged and existing
documentation is accurate, leave it unchanged; every task need not produce a
documentation diff.

This responsibility applies to repository-changing undertakings, including
standalone issues and epic children. The answer-only research route above
remains read-only and does not acquire documentation changes or a pull request
solely for this responsibility.

6 — Open the draft
------------------

This step and the following PR steps run only on the repository-change route.
The issue-only research route closes at `Implement` after recording its
complete answer on the issue.

Push the branch, then invoke `pr`: it owns the branch guard, the existing-PR
check, draft state, ongoing currency, and whether there is an issue to
reference — there is, and it is this one. The body closes it, and
`issue-deps` treats that line as the write into the graph. Its evidence test
has nothing to weigh here, because the edge is given by the assignment rather
than inferred: the issue being implemented is the issue the pull request
closes.

**On a resume the pull request is adopted, not replaced.** Pushes go to the
adopted branch, `pr`'s existing-PR check finds its open pull request and
updates it, and no second pull request is opened.

**Opening or reusing the draft starts supervision.** `pr` starts or reuses
common currency maintenance. The undertaking retains assessment of CI, review,
`The gate`, and `The milestone` while draft and after ready. Its active
harness reference names the continuation and any owner-resume limitation.

**The body is `pr-body`'s, and so are blockers that go with a Tofu diff.**
Where the branch changes the infrastructure Tofu stack, the body carries
`pr-body`'s apply-and-state blocker and the pull request the `human` label
while that action remains outstanding. A plan is a separate operation: it is
not a human action by default, and `Implement`'s escalation gate decides
whether its target, route and restrictions permit this session to run it.
`issue-labels`' `human` kind remains an issue classification, not this
temporary pull-request state.

**Undertake owns operational escalation.** `pr-body` publishes the decision
and evidence established here; it does not infer inability from a missing
tool, credential, network route, a Tofu diff, or an old blocker. On each
operation that might need a person, identify the exact blocked step and
classify it: unknown route, repairable execution failure, current-session
capability or access gap, external wait, or genuine human dependency. For an
unknown route, inspect relevant repository instructions, documentation and
Makefile routes, plus available tools and access without exposing secrets.
Attempt each available, permitted route; diagnose ordinary repairable
failures within this task's scope and the existing workflow bounds.
Documentation alone is not evidence that a route cannot run.

Capability is not authorization, and this session's capability is not the
task's actor requirement. Describe required credentials, connectivity, tools
and authorization directly, not as a laptop-, local-, cloud-, or human-only
task. An authorized agent with those capabilities may continue through an
available handoff under existing dispatch rules. If this session lacks access
and no authorized agent route exists, report the precise environment
prerequisite and resumption or handoff path; do not invent a dispatch
facility, transfer secrets, or call the work human-only. If a person must
provision access or approve an operation, isolate only that contribution from
the work an authorized agent can do.

An explicit production prohibition or required human approval is enough to
stop without a probe. Never test a prohibited operation, access production,
perform a dangerous action to see whether it fails, bypass authentication,
expand privileges, or treat a binary or token as permission. For `tofu plan`,
inspect its target, documented route and restrictions first: run an available
permitted plan without asking the user; do not run a plan against live
infrastructure in this task. The repository's human-only apply and
updated-state requirement remains.

Escalate only on an observed human dependency. State the blocked step, the
attempted route and its observed failure, or the exact restriction that
precluded an attempt, and request only the smallest contribution the person
can supply. Evidence can be linked; do not turn every PR body into a
transcript. Pending CI and other external waits stay with the existing
continuation; a recoverable execution failure is not a human blocker.
Complete independent permitted work before pausing unless a higher-priority
safety rule requires an immediate stop. On resume, revalidate the dependency
against current evidence, then remove satisfied or stale blocker text and the
corresponding PR `human` label while preserving unrelated labels. Keep every
still-valid apply, state, approval or other requirement.

**The push is what runs the project's gates.** The constitution's *Before you
call it done* sends them to CI rather than to this machine, so no local gate
step comes before this one. A red check is answered at `Fix, answer, resolve,
push`, and the ready gate below is what it has to satisfy in the end.

7–9 — `Review the head`, `Fix, answer, resolve, push`, `Verify the fix delta`
----------------------------------------------------------------------------

Invoke `review-cycle`. It owns the CI wait, full review, finding protocol, and
independent bounded verification. First record the reviewed SHA and every
finding disposition. Batch all fixes, including CI and bot fixes, push them,
and wait for CI on that head. Then run `Verify the fix delta` when the
pull-request content changed behavior, contracts, or workflow rules. It is one
pass for the batch, never one per commit or finding.

A pass that finds defects returns to `Fix, answer, resolve, push`, and the
correction pushed from there earns the pass that confirms it — every time,
because an unverified fix is what the round exists to prevent. The loop ends
on the first clean pass, and `review-cycle`'s wall ends it the other way,
with the defects reported on the pull request. How many passes that takes is
that skill's number, read there rather than carried here. An
unavailable reviewer or an incomplete pass keeps the pull request draft and
reports the blocker. Initial execution and a resumed session read the durable
review record before acting; a resume, a rewritten history, a bot finding and
a late CI correction are not passes and move nothing.

Only a material scope change runs a new `Review the head` round. A base merge
or history rewrite with unchanged pull-request content does not. `review-cycle`
owns the content comparison and rejected-finding evidence rule.

10 — Ready for review
---------------------

The harness pull-request client takes it out of draft only after `The gate`
below holds. It does not review; `review-cycle` supplies the full review and
independent verification that the gate consumes. The completion notice is one
of the gate's reads, so a round that closed without posting it is not yet
ready.

Once the pull request is ready, finish the Omp undertaking through its harness
route before reusing the session for another issue.

Marking a draft ready is a natural moment to reach for a review, and the
branch was already reviewed at `Review the head` — whether that review is
stale is `review-cycle`'s provenance test and is answered inside the round,
not here.
Where `review` is live rather than in `attic/skills/`, this is also what
discharges the leaving-draft trigger in its description: it fires on exactly
the moment this step occupies, and a round already run on this head is that
trigger already answered.

**A verified human dependency stops readiness here.** First revalidate each
reported blocker against current evidence, including on resume. Do not treat
the old body, label or an earlier agent claim as proof that the action remains
outstanding. If evidence shows it is satisfied or stale, update the body and
remove only its `human` label, preserving other labels; keep any separate,
valid requirement. Otherwise run the review round to its end first. Its
completion comment names the exact blocked step, the attempted permitted
route and observed failure, or the restriction that precluded an attempt, and
the smallest human contribution needed. The pull request stays a draft.
Complete independent permitted work before pausing unless a safety rule
requires an immediate stop. On resume, the person's contribution must be
reflected in current branch evidence — for Tofu, the apply and committed
updated state — and the changed head earns its review round before returning
through the gate. Pending CI and other external waits are not human
dependencies; follow their existing continuation instead.

**A missing tool is an unknown route, not yet a capability gap.** This holds
whichever step the session entered at, a resume included. Before a required
verification is called unmet for lack of a tool, apply `Open the draft`'s
escalation rule to it: inspect the repository's setup, install and Makefile
routes for that tool, and attempt the available, permitted ones in turn until
one provides it. Read each result. A failed `which` or `command -v` is not
evidence of a gap. A gap is established by an attempted route's observed
failure, by the exact restriction that precluded an attempt, or by an
inspection that found no documented route.

**A current-session capability gap is not a human dependency.** If a required
verification remains unmet because this session lacks credentials,
connectivity or another capability, use an available authorized-agent
handoff. If none exists, keep the pull request draft and report the exact
prerequisite and concrete handoff or resumption path; do not ask for a laptop
or apply the PR `human` label solely because this session lacks access. Finish
independent permitted work and the review round before pausing, unless a
safety rule requires an immediate stop. The gate remains unmet until the
required verification evidence is recorded.

When the gate clears, the milestone's moment has arrived: publish the
first-readiness report through `The milestone` below, before marking the pull
request ready. The report records that the ready-for-review gate cleared; it
does not claim the PR is already ready to merge. The existing supervision
continues without a second owner. A pull request that stops here on a human
action publishes nothing: it has not passed the gate, and a report naming
readiness over a bar only a person can clear is the false claim the gate exists
to refuse.

11 — Keep it current
--------------------

Invoke `pr`'s `Keep it current` and its active harness route. That skill owns
the base merge, cadence, CI floor, conflict handling, and watch lifecycle for
every agent-opened PR. `Open the draft` starts maintenance; this step reuses
it rather than waiting until ready or starting a second actor.

When it looks
-------------

Take `pr`'s catch-up look on every turn returning to the open pull request,
and once before `Ready for review`. Currency is the gate's first condition,
not proof that the undertaking is complete.

After currency settles, assess CI on the resulting head through
`review-cycle`'s `How to wait`, then continue review, the ready gate, and
`The milestone` when their conditions permit. Missing logs remain an
evidence blocker. A cap, review wall, human action, or evidence blocker
reports the outstanding condition and actual resume path; it does not reset
the bound, authorize a retry, or call the undertaking complete. Where the
harness has no owner continuation, report that limitation at `Open the draft`.

After the merge
---------------

Follow `pr`'s `After the merge` for current-head CI and its continuation
route. Failed checks return to `Fix, answer, resolve, push`.

**A clean merge earns no new notice either.** A completion notice that names
the pre-merge head still covers the merged head, by the first-parent walk
through merge commits that `The gate` reads. Where no notice exists at all, the
round at `Review the head` closed unpublished: post the notice naming the
current head once CI is green on it. Red CI after the merge goes to `Fix,
answer, resolve, push` as above, and the push that fixes it is a new head that
the round covers in the normal way.


A round after ready goes back to draft
--------------------------------------

**Return the pull request to draft before any push that changes
pull-request content** — a fix, a conflict resolution, a new commit — and so
before `Review the head` runs. Ready again through `The gate` below when the
round closes — the same gate, not a second one. A ready pull request is liable
to be merged without notice, and a person merging from the GitHub UI reads no
completion notice. Pushing to it first leaves unreviewed content on a pull
request that says it is ready. A pull request under review is not ready for
review, and a reviewer must not be reading a branch that is changing
underneath them.

**A clean base merge at `Keep it current` is the exception.** It changes no
pull-request content, earns no round under `After the merge`
([`0022`](../../docs/notes/0022-the-merge-is-mechanical.md)), and does not
return the pull request to draft. A merge resolved by hand changes content
and is not the exception.


The gate
========

The hand-typed prompt this skill replaces got three things wrong. Two of them
were about the round rather than the sequence and left with it — `review-cycle`
carries *review once per diff* and *a briefed reviewer with a publication
contract, not a bare dispatch*. The third is
this skill's, and it is the one `Ready for review` turns on.

Ready is a gate, not a step
---------------------------

"After fixing, set the PR to ready" reads as unconditional. It is not. It is
also not a judgement: **the gate is a read**. Eight conditions decide it, seven
reads answer them, and every read is a call the reference file for the harness
in use names. A gate that has to be weighed is a gate that gets taken to the
user, and the user is not the one who can answer it.

Take the reads in this order. The first that does not hold is where the
sequence stops, and the reason is stated in one line. Cite a read by its
condition, never by its position: a read inserted ahead of it moves every
number.

1. **The head carries the whole of the issue's work.** Four parts, each a call
   or a comparison of two texts the session already holds:
   - The task worktree has no uncommitted change: `git status --porcelain`
     in the task worktree prints nothing.
   - The branch has nothing unpushed: `git log @{upstream}..HEAD --oneline`
     in the task worktree prints nothing.
   - Every item in the issue's acceptance section — `issue-body`'s
     requirement 5, the `Acceptance and verification` heading in the bodies
     this toolkit writes — maps to a file in the pull request's diff, or is
     answered on the pull request with a reason. Take the issue body as read
     at `Read the issue and its edges` and the diff through the route the
     reference file names. Name each item and the diff file that satisfies
     it. An item with no file and no reason is unmet.
   - The session has no further change planned for this branch. A planned
     change is work at `Implement` now, before the gate; never after ready.

   Where the read does not hold, the sequence returns to `Implement`, and
   comes back through the push, the round and the gate. The pull request stays
   a draft, and the reason is one line naming the unmet item. This is not a
   stop and not a question: it is the sequence not yet at the gate. This read
   comes first because every later read is about the head a reviewer will
   read and a person will merge. A head that is not whole is not that head,
   so reads taken on it answer about a commit that will not be the one
   merged — the same reasoning the merge read gives for its own place.
2. **The branch against its base**, for the condition that it is current and
   merges cleanly. GitHub's merge state answers it, and only three of its
   values are this read's: `behind` is a base the branch does not carry, so
   `Keep it current` runs its merge and this read is taken again; `dirty` is
   that step's conflict; `unknown` is GitHub saying it cannot answer yet,
   which is a wait under `review-cycle`'s `How to wait` rather than either
   answer. This read comes first because the merge moves the head: every
   condition below is about the head a reviewer will actually read, and a
   merge run after them would leave them answered about a commit nobody sees.

   **The other values are not this gate's business, and reading them as
   stops is what jams it shut.** A draft reports `draft` or, where the
   repository requires a review, `blocked` — measured on a draft of this
   toolkit with every check green and the branch current, 2026-09-18, which
   answered `blocked`. Neither establishes a branch-currency failure:
   `draft` is the state this gate exists to change, and `blocked` does not
   identify its cause. Read CI and actual review requirements separately;
   do not infer required approval from the enum. Holding a draft until approval
   can stall the transition that requests that review. `has_hooks` is a
   passing state with a hook configured.
   **`clean` is not a gate condition**: the report is published while the PR is
   still a draft, after the gate's independent reads establish currency and
   green CI. The milestone does not wait for a post-ready merge-state read.
2. **CI on the head commit**, for the condition that it is green. Read the
   checks themselves rather than inferring them from the merge state, which
   reports a draft's status before its checks': the union of check runs and
   commit statuses that `review-cycle`'s wait reads is the same union here,
   and the reference file names what answers it on this harness. **Pending
   is not green** — wait for it the way `How to wait` says, rather than
   treating an unreported check as either answer. The mechanism has one
   home, and it is not this one.
3. **Every review thread**, from any reviewer and not only from the round at
   `Review the head`. This read answers two conditions, which is why six
   reads close over seven: no thread is unanswered or unresolved, and every
   finding that round raised is fixed, or rejected with a reason on its
   thread, or deferred with the user's agreement. An open thread is work at
   `Fix, answer, resolve, push`, never a reason to stay draft.
4. **The review record on the pull request.** The independent verification
   record for the scope is clear on the current behavioral head: the last
   pushed fix has a pass that found nothing. The bound on those passes is
   `review-cycle`'s, cited here rather than restated — and its wall is the
   opposite of this condition, never a way through it. A walled scope has
   outstanding defects and stays a draft, as do an incomplete pass and an
   unavailable reviewer. **A full review that raised no actionable finding
   leaves nothing to verify**, and this condition is satisfied with no pass
   owed — a clean review produces no verification record, so waiting for one
   waits forever.
5. **The completion notice covers the current head.** Read the pull request's
   conversation comments to the last page and take the latest comment that
   starts with `## Review cycle complete! 🎉` and is written by the account
   that posted the claim. The read holds when the SHA it names is the current
   head, or an ancestor of it reached by walking the head's first parents
   through merge commits only.
   This is the test `embark`'s `Land the pull request` applies in its fourth
   read, cited here rather than restated. **A missing notice is work, not a
   stop.** When the earlier reads hold and this one does not, the round
   closed unpublished: post the notice for the current head through
   `review-cycle`'s notice route, then take this read again. The gate never
   marks ready on a notice it has not read.
6. **The pull request waits on no human action.** The `Blockers` section's human-action
   bullet marks a pull request whose Tofu changes must be applied, and the
   updated state committed, before it merges — a bar only a person clears,
   and unlike a pending check nothing will ever report it. `Ready for review`
   pauses on it; this condition is what the sequence returns to once the
   branch carries the result.

**When the reads agree, publish the first-readiness report if none exists,
then mark the pull request ready in the same turn.** The harness calls are in
`The milestone` and the reference file; no summary, permission request or
turn boundary comes between the gate and these actions. A failed report write
leaves the PR draft. If marking ready fails after the report posts, preserve
the report and revalidate the gate before retrying.

**The user is never a gate condition.** Every stop this sequence takes is
named under `Where it stops and waits`, and none of them is a confirmation
that the work is ready. The reads above are the only thing that knows. The
user did not do the work and cannot answer for it, so a question here asks
somebody else to carry a claim this session is the one holding the evidence
for.

A branch behind its base, red CI, an open thread, or a human action still
owed, or an issue item the diff does not carry, means it **stays a draft**,
and the reason is stated in one line. A red pull request marked ready is a
claim about the work that is not true, and so is a ready one that does not
merge. **A partial pull request marked ready is that false claim in its
plainest form.** It says the work is done, and a person merges a ready pull
request without reading the round's record, so the claim is acted on: #558
passed every other read, was marked ready at 16:29 UTC on 2026-10-06 and was
merged two minutes later without the fixture #555 required. **So is a draft that satisfies every
condition**: it tells a reviewer there is nothing to read yet, which is the
same false claim pointing the other way, and "left in draft to be safe" is
the sentence it gets written in.

The gate is also what a round at `Keep it current` returns through. That round
sends the pull request back to draft, and these conditions are what let it out
again — the same ones, read again, rather than a second gate written for the
second round.

[`0021`](../../docs/notes/0021-the-gate-is-a-read.md) is the decision, and the
two stalls that prompted it.
[`0031`](../../docs/notes/0031-ready-means-the-work-is-whole.md) adds the
completeness read, and the draft before a content push.


The milestone
=============

The first-readiness report records the first time an undertaking passes the
ready-for-review gate. Publish it on the pull request after every condition in
`The gate` holds on the current head, but before `Ready for review` marks the
pull request ready. The reference file for the harness in use names the calls
that read the claim's timestamp, find an existing report and post it.

**The report is a milestone, not the end.** Posting it does not mark the
pull request ready by itself, stop the watch at `Keep it current`, stop a
process or cancel a scheduled wake, close the issue, or merge anything. The
watch's exits — merged, closed, or the user says to stop — are what they were
before the comment existed, and a base-branch advance after it runs the same
update, CI wait, and return through the gate as any other.


Ready-for-review gate, not merge readiness
-----------------------------------------

The report states that the ready-for-review gate passed. It does not state
that the pull request has already left draft or that every later merge
requirement is satisfied. It is published only when all of these hold on the
current head:

- `The gate` holds — the round at `Review the head` has completed
  successfully, and every condition in the gate is satisfied on this head.
- The pull request is still a draft. The report is the required action before
  the harness marks it ready.
- The branch is current with its base and has no unresolved conflict, as
  established by the gate's currency read and `Keep it current`. The report
  does not wait for the post-ready mergeability answer.
- Current-head CI is green, review threads are resolved, the completion notice
  covers the head, and no human action remains owed. A pending check, an
  unresolved thread, a missing notice or a human blocker keeps the report
  unpublished.

The draft merge-state value is not affirmative evidence: `DRAFT` and
`BLOCKED` can mask branch currency or other mergeability. The gate uses its
independent reads for currency, CI, reviews, threads, the completion notice
and blockers. It does not infer that a masked state is clean or wait for a
post-ready `CLEAN` state before reporting.

Any missing condition keeps the comment unpublished and the sequence watching.
A report that says the ready-for-review gate passed while a check is pending
is the same false claim a red pull request marked ready would be.


What the report carries
-----------------------

- **The timing, labelled as what it is** — wall-clock time from the claim to
  the first successful ready-for-review gate. It runs from the claim comment's
  timestamp, read back off the issue through resumes and later draft states.
  The claim's timestamp is the durable start, so a session arriving late never
  restarts the clock. After the gate reads pass, capture the current UTC time
  immediately before posting the report; that is the milestone timestamp.
  Preserve the telemetry-readable line shape:
  `Elapsed: <duration>, from claim (<UTC timestamp>) to first ready-for-review gate (<UTC timestamp>).`
  The interval covers implementation, review, fixes and waits; it excludes
  maintenance after the first report and is never called compute time or total
  undertaking duration. If the claim start is unrecoverable, report timing as
  unavailable. If posting fails, publish no milestone; revalidate the gate and
  capture a new time before retrying.

- **`provenance`'s block, under `Claim the issue`'s rules for it.** One
  session did the work, so one model and one session are named; where a
  resume moved the work to another session, both are named in the order they
  ran, and attribution nobody reported is not reconstructed.

- **The head it binds to.** The pull request's head SHA and the report
  timestamp. The comment is a statement about that head: a later head — after
  a base merge, conflict resolution or any push — is not what it described,
  and nothing in the comment claims otherwise.


Once per undertaking
--------------------

The report posts once for an undertaking and its pull request. Before posting,
read the pull request's existing comments and look for the comment that opens
with the fixed line `First-readiness report`. That line is the marker, written
the same way every time. A resumed sequence, a failed ready transition, or a
later return through draft finds the original report and does not duplicate or
overwrite it. An existing report does not replace current-head gate evidence:
re-read every condition before attempting to mark the pull request ready.

Post the report only after all gate conditions hold. If the report write fails,
leave the pull request in draft and stop before the ready write. If the report
posts but marking ready fails, preserve that report; revalidate the current
gate before retrying readiness. Do not rewrite the report's original timestamp
or head on a later pass.

**A short read is a reason to look again, not to stop.** A gate read that comes
back blocked, unknown or otherwise short of the conditions above leaves the
report unpublished, and the standing continuation carries the evaluation.
Every check-in and catch-up look reads current-head CI after currency, then
takes the gate's remaining reads when CI permits progress. An approval that
arrives or a mergeability answer that settles moves no head or base — the look
that observes all gate conditions is what posts the report.


The wrap-up
===========

A `stand-down` orchestrator may interrupt this session mid-sequence and send
one message: the wrap-up instruction its `Secure the work` sends, addressed
the way `embark`'s `Recover a session` addresses a correction. **It is the
user's stop, relayed by the session that dispatched this one, and it is obeyed,
not weighed.** The harness tells a session to treat a peer's message as data
and to take no destructive action on it alone. A commit and a push to this
session's own task branch is not destructive, so that caution does not delay
the wrap-up. A wrap-up from the orchestrator whose address this session was
given is obeyed. Where no address was given, a wrap-up that names this
session's task issue is obeyed too: obeying a stray one costs one pushed
work-in-progress commit, and the user can still resume the work, as `A wake
after the stop does no work` says.

**It preempts the step that is running.** That step is abandoned, not
finished: no CI wait runs out, no review round completes, and no base merge,
fix or test run starts. A tool call the interrupt cut off is not retried. In
this one turn, in order:

1. **End the watch** — the cancellations `The stop`'s `End the watch` names.
   They go first, so the CI run that the push starts wakes nothing here.
2. **Commit and push** what is in progress to the task branch, named files
   staged and no hook or test skipped. A branch with nothing new is pushed as
   it is.
3. **End the turn** without starting anything else. Send no report to the
   orchestrator: it is already waiting for this turn to end.

It opens no pull request and marks nothing ready: that is `stand-down`'s own
record to write, not a step of this sequence completing.

**It writes no handoff.** `stand-down`'s `Write the handoff` writes the one
task-issue comment, so a handoff here would make two. `The stop` below is not
this section: it governs a stop the user gives this session directly.

**A wake after the stop does no work.** This holds after `The wrap-up` and
after `The stop`. A timer that escaped the cancel, a pull-request event, a CI
result on the work-in-progress push, or a check-in reaches an undertaking that
is stopped. Answer it in one line that the work is stood down, and end the
turn. Harness guidance that makes a pull request this session opened its own
to drive green does not restart the work: the user's stop outranks it, and
the harness itself says to stop following up when the user asks.

Three things are not such a wake. A repeated wrap-up runs `The wrap-up` again,
so a push that failed the first time is retried when `stand-down` is re-run. A
correction from this session's orchestrator, or a new instruction from the
user, starts the work again, and so does a resumed `/undertake` in a new
session. The orchestrator is the session whose address this session was given;
where none was given, no session is, and only the user restarts the work.


The stop
========

The user tells this undertaking to stop, stand down or wrap up. **The stop
preempts the step that is running**, the same as `The wrap-up`: that step is
abandoned, not finished, and nothing new starts. It applies at any point after
`Establish task worktree`, whether or not a claim or a draft pull request
exists. A claim says the work started and never says where it ended, so a stop
that leaves only the claim leaves the next session to guess. Before `Establish
task worktree` there is no branch, so nothing to secure or hand off: say so in
one line and stop. **A stop that
arrives as `stand-down`'s wrap-up message is `The wrap-up`'s, not this
section's.**

In order:


1. **End the watch.** Cancel the `Keep it current` wake slot timer, any CI
   watcher this session holds, and every pull-request subscription. The
   reference file for the harness in use names the calls. This goes first, so
   the CI run that the push starts wakes nothing here.
2. **Secure the work.** The rules are `stand-down`'s `Secure the work`: commit
   work in progress to the existing task branch, stage named files, skip no
   hook and no test, and push. A branch with nothing new is pushed as it is.
3. **Write the handoff.** One comment on the task issue:

   ```markdown
   ## Handoff — undertaking stopped <UTC timestamp>

   This session stopped at the user's instruction. The work is yours to reclaim.

   - Branch: `<remote push branch>` — <link>. Local execution branch:
     `<local branch>` (omit this line when it is the same branch). Pushed head:
     `<sha>`.
   - Pull request: <#N and state (draft / ready), or "none open">.
   - Reached: <the last step of the sequence completed>.
   - Outstanding: <what is blocked, failing, or unverified — failed checks,
     open review threads, a human action owed — or "nothing known">.
   - Environment: <each tool or credential the outstanding work needs, with
     the repository route that sets it up, e.g. "`omp`: `make evals-install
     && make evals-setup-omp`" — or "the checkout alone">.
   - Resume: <the concrete next action, e.g. "run `/undertake #N`; it resumes
     on the branch above">.
   ```

   It ends with `provenance`'s block and carries no verse: somebody acts on
   it, the reason `stand-down`'s task handoffs carry none. A push that fails
   is stated here: `Pushed head:` names the last head that reached origin,
   `Outstanding:` names the failure, and the handoff is still written.
   **The handoff is filled from what this session already knows**, plus the
   git read the reference names for `Pushed head:`. No test or CI check is
   run, no CI wait is finished, and nothing else is investigated to fill a
   field: what is not known is written as unknown.
4. **Stop.** The undertaking does not mark the pull request ready, does not
   close the issue, and does not call the work complete.


**Idempotent.** Read the issue's comments before posting. A `## Handoff —`
comment that names the same pushed head, posted after the latest claim comment
— or anywhere, when the issue has no claim comment — is an equivalent
handoff: post nothing. One that names an older head is not
equivalent, so post a new one. This is `stand-down`'s `Idempotent re-entry`.

**An embark-dispatched implementor the user stops directly** runs `The stop`
and also sends the stop to its orchestrator under `Reporting to an
orchestrator`. `stand-down` counts that handoff as present where it names the
current pushed head.


Reporting to an orchestrator
============================

An undertaking `embark` dispatched may be handed the address of the session
that dispatched it — its orchestrator. **Where no address was given, this
section does nothing**, and the sequence runs exactly as it does without it.
Where one was given, the sequence reports to it at three moments:

- **Every stop**, from `Where it stops and waits` or from `review-cycle`'s own,
  with the question it asks or the condition it reports.
- **`Open the draft`**, once the draft exists.
- **`Ready for review`**, once the pull request is marked ready.

Each report opens with the fixed line `Implementor report for #<task issue>`,
then names the pull request where one exists, the moment reached, and the
question or condition where there is one. The orchestrator finds reports by that
line.

**A report is sent, not a conversation.** It never waits for an answer, and
the stop it reports still stops. An answer arrives, if it comes, as a message
from the orchestrator, and the sequence reads it as it reads any other.
**A report never replaces the record**: the question still goes on the pull
request or the issue where `Where it stops and waits` puts it, because the
record outlives both sessions and the report does not.

**A failed report is reported, not retried in a loop.** Say once, in the
session, that the report did not go, and carry on with the sequence. The
orchestrator's GitHub watch still sees the pull request.

The reference file for the harness in use names the route.


Where it stops and waits
========================

Autonomy is the point, so each pause has to earn itself. Fifteen stop the
sequence. Eight stop it to *ask* — the ambiguous issue, the request too vague
to write one for, an issue labelled `proposal`, an issue carrying two of the
six labels, the failing approach, a designated branch the harness states
ambiguously, more than one existing task branch on the issue's record, and a
base merge whose conflict is a real one. A blocked issue,
an epic, an issue labelled `human`, running or failed CI, a review wall, a
human action owed, and a current-session capability gap with no authorized
handoff stop it to report the unfinished condition and actual resume path.
Where an orchestrator's address was given, every stop is also reported to it
under `Reporting to an orchestrator`.

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
  user's and decomposing it is `epic`'s; a `human` names work no agent can
  do, so the person it waits on is the answer; an issue carrying two of the
  six answers the readiness question twice and answers it neither way.
  `issue-labels` is what each label claims, and what a contradiction between
  two of them costs.
- **More than one distinct existing task branch** on the issue's record, or a
  pull request from a fork the session cannot push to, at `Read the issue and
  its edges`. Report the branches and ask which to resume; never guess.
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
- **A genuine human dependency still owed**, at `Ready for review` or the
  operation that exposes it. `undertake` owns escalation: classify the
  blocked step, investigate unknown routes, attempt available permitted
  routes, and repair ordinary failures within scope. Stop without an attempt
  only where an explicit prohibition or required approval precludes it. Never
  probe production or a dangerous operation. A genuine escalation names the
  attempted route and observed failure, or exact restriction, and asks only
  for the missing human contribution. Finish independent permitted work first
  unless safety requires an immediate stop. On resume, revalidate current
  evidence and clear satisfied or stale blocker text and its PR `human` label
  without removing unrelated labels or valid outstanding requirements. A
  Tofu apply and updated-state commit remain human-only.
- **A current-session capability or access gap with no authorized-agent
  handoff**, at `Ready for review`. This is not proof the work needs a human.
  A missing tool is not this stop until `Open the draft`'s escalation rule
  has run on it: its documented routes were attempted and failed, a
  restriction precluded them, or inspection found none.
  State the exact required credential, connectivity, tool or authorization
  capability, and the concrete handoff or resumption path. Do not describe a
  step as laptop-, local-, cloud- or human-only when capabilities, not device
  or actor, are the requirement. Do not invent a dispatch facility or transfer
  secrets. Keep the PR draft until the verification evidence exists, and do
  not add the PR `human` label solely because this session lacks access.
- **Pending CI and other external waits** are not human actions; retain
  ownership and use the existing continuation rules.

The round at `Review the head` and `Fix, answer, resolve, push` has three stops
of its own — its own wait on CI, a review finding whose fix is a real
trade-off, and fixes that will not converge, which is the wall at `Verify the
fix delta`. All three are `review-cycle`'s; the second is `judgement-call`'s
gate applied inside it, and the third reports rather than asks.

Everything else runs through. No permission is asked to open the issue, to
claim it, to commit, to push, to open the draft, or to mark it ready. The last
of those is the one most often asked for anyway, and `The gate` is why it is
not: readiness is read, so there is nothing a confirmation could add.


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
  to the user; it is not this run's second issue, except a confirmed Daily
  Driver component defect reported under `issue`'s automatic-reporting policy.
  That narrow report does not authorize undertaking unrelated fixes.
- **Does not review, and does not answer a review.** The round is
  `review-cycle`'s, and it is reachable without this sequence: a pull request
  opened by hand, or one a reviewer has come back to, gets the same round
  without an issue anywhere near it.
