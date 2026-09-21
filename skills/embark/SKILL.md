---
name: embark
description: >-
  This skill should be used whenever an epic's task issues are put to
  work in more than one session at once, or a fleet already at sea is
  watched — when the user says "/embark", "work the epic", "launch
  the wave", "start the next wave", "run these issues in parallel", "open a
  session for each of these", or "how is the epic going", and on Claude's own
  move from a planned epic to opening a session per task — a web session on
  Claude Code, one harness-local subagent per task on Omp and Codex. Supplies
  the graph-derived wave, each task's implementor, the muster roll, the
  pull-request watch, merge-ready landing, the epic close, and the
  quiet-session backstop. Not for decomposing work, which is `epic`, taking
  one task issue to a pull request, which is `undertake`, or a single issue.
---

# Embark

An epic in, a fleet of sessions out, each merge-ready pull request landed,
and the epic closed when the last task is home. `epic` decomposes the work and
stops; this skill works it, wave after wave, unless the user keeps landing by
hand.

It is an orchestrator, in the same shape as `epic` and `undertake`: **it
invokes, it does not restate**. The decomposition is `epic`'s, taking one task
issue to a pull request is `undertake`'s, the graph reads are `issue-deps`',
the name a session carries is `session-title`'s, and the engineering standard
is the constitution's. Where a step below names a rule one of those owns, it
names it as a pointer and cites the owner — a rule that acquires a second home
is one whose copy goes stale.

What this skill owns is the dispatch, the watch, and the landing: which tasks
sail together, what is written down as they sail, what is done about one that
does not come back, and when the finished fleet closes its epic.

**The routes are per harness, and they live beside this file.** Every call the
steps below need is named in words here and resolved to a route there:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi,
[`references/codex.md`](references/codex.md) for Codex. Read the one for the
harness in use before `Read the epic`, which is the first step with a route in
any of them. **All three are tables.** Claude Code's names the web-session
route; Omp and Codex cannot open a web session — one has no client, and the
other has one this skill cannot reach — so their files carry the
harness-local subagent fallback `Open the sessions` takes instead, and record
what each surface has and has not been measured to do.

**Every step has a name, and the name is how it is cited.** The numbers order
the sequence and do nothing else: insert one and all of them move, while a name
stays where it was put.
[`0005`](../../docs/notes/0005-steps-are-cited-by-name.md) is the decision and
`scripts/check-step-names.py` is what enforces it.


The sequence
============

| # | Step | Owner |
| - | ---- | ----- |
| 0 | `Read the epic` | this skill, `issue-deps` |
| 1 | `Title the session` | `session-title` |
| 2 | `Take the wave` | this skill, `epic` |
| 3 | `Open the sessions` | this skill, `undertake` |
| 4 | `Post the muster roll` | this skill |
| 5 | `Watch the wave` | this skill |
| 6 | `Land the pull request` | this skill, `undertake`, `review-cycle` |
| 7 | `Recover a session` | this skill |
| 8 | `Close the epic` | this skill, `epic` |

`Take the wave` is the loop point rather than `Read the epic`, and it is the
router: a wave that comes in returns there, the epic is read again from GitHub
because the graph moved while the fleet was out, and what it finds decides
whether the next wave sails, the watch resumes, or the epic closes.
`Land the pull request` and `Recover a session` are reached from `Watch the
wave`, and each returns there.

0 — Read the epic
-----------------

The epic's body, its sub-issues, and the blocked-by edges among them. Reading
the graph is free and needs no confirmation; `issue-deps` says so.

**An issue with no sub-issues is not an epic**, and that is the stop of that
name below. A task issue handed over is `undertake`'s, and work not decomposed
yet is `epic`'s.

Read the epic's comments too, because `Take the wave` needs to know which tasks
are at sea already.

1 — Title the session
---------------------

`session-title` has the form and the budget, and for this session it is the
orchestrating-an-epic form that skill defines. This session is the one the
user watches the fleet from, so it is named for the epic rather than for any
task in it.

Where the harness cannot set a title, that stop is the step's rather than the
sequence's: say so in a line and go on to `Take the wave`.

2 — Take the wave
-----------------

The batch that sails together: every open task issue of this epic whose
blockers are all closed, less the ones already at sea.

**The graph decides what can run; the epic's `Sequencing` decides what does.**
The two are not the same question, and `epic` writes both on purpose:

- **Blocked in the graph, placed early in the body** is a disagreement. The
  graph wins — `epic` says so, and says the body is fixed in the same turn.
- **Unblocked in the graph, placed in a later wave by the body** is not a
  disagreement. It is the scheduling choice `epic` requires that task's line to
  state, and it is honoured: the task waits for its wave.

**A `human` task is not in the wave.** Its label says no agent can do the
work, so a session opened on it would stop at `Read the issue and its edges`
and nothing else. It waits for the person, and `Post the muster roll` gives it
a row of its own rather than leaving it unaccounted for.

**Already at sea is read from the record, never assumed.** A task is at sea
when a muster roll on the epic names a session for it, or when its own issue
carries an `undertake` claim comment. Either is enough, and the second is what
covers a task somebody started by hand. A session is opened once per task, not
once per invocation of this skill — re-entering after the watching session died
is the case this rule exists for, and launching a second session on a task
already claimed is two agents writing one branch.

**The latest entry wins.** `Recover a session` posts a replacement entry when
it retires a session, so a task named twice on the epic is read at its most
recent one. The earlier entry names a session that is gone, and reading it is
how a resumed watcher loses the live one. The latest roll also carries the
landing mode, so a resumed watcher reads it rather than choosing again.

**A claim from a session this skill did not open is worth a line to the user**,
and is still not a reason to launch a second one. That collision is the thing
`undertake`'s claim exists to make visible.

**An empty batch is four different things, and only one of them is a stop.**
This step is the router, and the wave that comes in at `Watch the wave` returns
here to be routed again:

- **No open task issue left at all.** The epic is worked out. Go to `Close the
  epic`.
- **Every task still open is at sea.** The fleet is out and this session has
  nothing to launch — which is exactly the state a watcher resumed after the
  last one died finds. Go to `Watch the wave`, over the tasks at sea.
- **Every task still open is blocked by something open.** There is no wave.
  Name the issue that blocks, and wait: that is the stop of that name below,
  and it is the only one of the four.
- **Every task still open is `human`.** There is no wave, and there is nothing
  to wait for either: no agent can start on any of them, and nothing this
  session does moves them. Post the roll over them, say that the epic is
  waiting on a person and name what each one needs, and stop.

3 — Open the sessions
---------------------

**Where the harness can open web sessions, one session per task issue in the
wave**, opened in the same environment as this one, all of them before the
watch starts. **Where it cannot, the fallback is one implementation subagent
per task issue, dispatched concurrently through the harness's own subagent
surface** — a wave is one batch either way, and every ship in it carries four
things and no more:

- **A prompt naming its task issue and asking for it to be undertaken**, and
  nothing else. The issue is the statement of the work; a summary of it in the
  prompt is a second copy that can disagree with the first, and the session
  reads the issue itself at `undertake`'s `Read the issue and its edges`. The
  boundary holds in the fallback: the subagent is given the issue number and
  the instruction, no more.
- **The model the task issue records**, taken from the `Model:` line that
  ends the task body, written under `issue-body`'s contract. Where there is
  no such line the session inherits this one's model, which that contract
  states is the working default.
  **This skill does not choose**, and does not second-guess a line it is
  given: the judgement was made when the task was sized, and re-making it here
  on less information is how it gets made worse. That binds the web route.
  **In the fallback the line is advisory, and the default is a cheaper
  implementation model** — an unattended routine edit does not need the
  orchestrator's own strength, and quota spent on one is quota the rest of
  the wave does not get. Two exceptions, both the orchestrator's judgement
  and neither appealed: work that is security-sensitive, and work whose
  complexity makes a weaker implementor unsafe. Either is dispatched to a
  stronger implementor — a stronger subagent or session, never the
  orchestrator itself. **Delegation is unconditional**: the orchestrator
  keeps responsibility for claim, dispatch, watch and gates, and never
  implements. A task too
  underspecified for any subagent is a planning defect, not an escape
  hatch — its body failed the readiness test, and the fix is a tighter
  task body through `epic`, never the orchestrator's hands on the code.
- **A title**, in `session-title`'s form for the task issue. It is what makes a
  list of five running sessions readable at the moment the wave launches,
  which is before any of them has reached its own `Title the session` and set
  the same string. Where the dispatch surface takes no title, the issue
  number in the prompt is the identifier the muster roll carries instead.
- **The environment's own permissions**, inherited rather than narrowed or
  named. A task session runs unattended, and a session opened in a mode that
  blocks for a human approval is a session that never starts work.

**An implementor may ask for help, and must have someone to ask.** The route
is the harness's agent messaging, and the advisor is the orchestrator itself
or one shared subagent running a strong model — one advisor for the wave,
never one per task unless a task's context is genuinely separate. An
implementor that fails silently instead of asking is the failure this rule
exists to surface, and advisor-on-demand alone does not catch it.

**So a strong-model review gates every pull request an implementor
produced.** An implementor that reaches `undertake`'s ready gate does not
take the gate itself: it hands its head to the advisor over the messaging
and waits, and the strong model — the orchestrator or the shared advisor —
runs `review-cycle`'s round and returns its findings the same way. The
implementor answers them under the round's protocol, and `Ready for review`
waits for the round to close. The implementor does not review its own work,
and a reviewer at the implementor's own strength is not a review.

**A dispatch that fails sinks one ship, not the fleet.** A model identifier
the session client rejects fails the call rather than falling back; report
that task, launch the rest of the wave, and do not substitute an identifier
of your own — the constitution forbids the guess, and `issue-body` owns the
line that was wrong. The same holds in the fallback: a subagent that fails to
launch is reported, and the rest of the batch sails.

No permission is asked here. `Waves launch without confirmation` below is why.

4 — Post the muster roll
------------------------

One comment on the epic as the wave launches, and it goes up **after** the
sessions are open, because it records their identifiers.

It is what this skill does instead of asking, so it has to be readable by
somebody who did not ask for it. The wave's heading from `Sequencing`, and then
one row per task:

```markdown
### Wave 2 — after #143 · in progress

Landing: orchestrator

| Task | Session | Model |
| ---- | ------- | ----- |
| #144 — Validate against the schema. | [session_01AbC…](https://claude.ai/code/session_01AbC…) | `claude-sonnet-5` |
| #147 — Document the format. | [session_01DeF…](https://claude.ai/code/session_01DeF…) | `claude-opus-5`, inherited |
| #149 — Rotate the deploy key. | none — `human`, waiting on a person | — |
```

**Landing is read once from the invocation and written into the roll.** The
default is `Landing: orchestrator`. An explicit request such as "leave the
merges to me" writes `Landing: by hand` instead. `judgement-call` does not
fire: the user's words decide who lands the pull requests. Every later
invocation reads the latest roll and keeps that mode.

**A `human` task gets a row and no session.** It is in the wave's heading
because a reader counting the epic's open work would otherwise have to go
looking for it, and the row says why no session is named. A wave that is
nothing but `human` tasks still posts its roll: the roll is what says the
epic is waiting on a person.

**Say which model was inherited.** A reader cannot otherwise tell a judgement
`epic` made from a default nobody chose, and the difference is the whole reason
the `Model:` line exists.

**The fallback's roll names subagents, not sessions.** The columns are the
task, the implementor's subagent identifier, the model it ran on, and any
advisor — the dispatch decision made visible, which is the point of the roll.
A web-session row links; a fallback row names what the harness's own listing
resolves. `Say which model was inherited` holds in both: where a fallback
implementor ran on the cheaper default rather than the task's recorded line,
the row says so.

**The wave headings carry state, and nothing else moves it.** `epic` writes
that state into the epic's `Sequencing` at decomposition time and never
returns. This skill marks a wave `in progress` as it launches and `done` as it
comes in, in the epic's own body. That is the one edit this skill makes to an
epic body; everything else about it is `epic`'s.

**Those two words are the whole vocabulary**, because they are `epic`'s and
`epic` owns the format. A third state invented here — *at sea*, however well it
reads — is one `epic` does not know, and its `Fill in the epic` replaces the
body outright, so the invention survives exactly until the next edit there.

5 — Watch the wave
------------------

**The watch runs through GitHub, not through the session client.** Sessions can
be opened, interrupted, archived and messaged, and none of that reads back what
one is doing. Pull requests do: each task session produces a branch and a pull
request, and a pull request reports its own checks, its review threads and its
merge. It is also where the user is already looking, and it outlives the session
that opened it.

**A fallback wave is supervised through the harness's subagent lifecycle.**
The orchestrator holds the dispatch handles, and each subagent's result — or
failure — arrives as a wake of its own. No session client and no durable
cross-session timer is required for that, which is why their absence is not a
stop. The GitHub watch runs on top of it unchanged: it is still how work in
progress is told from work stuck. The lifecycle ends where the implementors
finish, though: a subagent's completion wake is spent by then, its pull
request still open, and a merge after it is something only the surface can
deliver. Where the harness carries no pull-request event and no durable
timer, the close of the wave — the wave marked `done`, the next one
launched — is resumed by the next `embark` invocation, and that is said
once rather than claimed as a watch.
So on every wake:

- **Subscribe to each task's pull request** as it appears, once. Events then
  start a turn on their own.
- **Send every task pull request through `Land the pull request`.** That step
  reads the gate and returns here, whether it merges or waits.
- **Read the epic's graph.** A task issue closes when the pull request that
  names it merges, and that is the test for a task being home — not the session
  status, which reports a session that has stopped, never a job that is done.
- **The wave is in when every task issue in it is closed.** Mark the wave `done`
  in the epic's body, and go back to `Take the wave`, which routes what happens
  next — the following wave, or `Close the epic`.
- **A task that is home has no session left to run, archived once.** When a
  task issue closes, archive the session that carried it: its branch is
  merged, so `undertake`'s `Keep it current` cadence has nothing left to
  merge and its review threads have nothing left to answer. **Not one
  moment earlier.** A session whose pull request is merely green and
  waiting on a reviewer is still working — it holds that cadence and it is
  what answers the next review comment — and archiving it there stops both
  silently, with nobody else holding the branch. **Once per task, not once
  per wake**: a later wake that re-reads the graph for a still-open
  sibling task finds this task closed again, and finds its own muster roll
  comment already posted for it — read that before archiving a second
  time. In the fallback the ship is a subagent that has already ended, so
  there is no session to archive. **The muster roll records the archive**:
  one comment naming the task and the session retired, the way `Recover a
  session` records a replacement minus the session that took over, since
  none did.
- **A pull request closed without merging is somebody's decision.** Its task
  issue stays open and its session is spent, so nothing here re-dispatches it:
  say which task it was, and leave it to the person who closed it.

**This skill does not manage the branches.** `undertake`'s `Keep it current`
already merges the base branch into each head on its own two-minute cadence, so
a sibling whose base moved heals itself, and a real content conflict stops that
session rather than this one. An orchestrator resolving a conflict in code it
never wrote is the wrong hand on the tiller.

**One wake slot, and a turn never ends with it empty** while a wave is at sea.
[`0010`](../../docs/notes/0010-the-wake-slot-is-never-empty.md) is the rule,
and it is the same one `undertake` and `review-cycle` hold — one durable timer,
kept by the identifier the call returned, filled again before the turn ends
whenever it is empty. A wake that finds the timer still in flight arms nothing.

**The backstop prompt carries the posture, because the wake will not.** The
prompt written for the next check-in is read on arrival, while this file is
not, and the wake it lands in — like every pull-request event beside it —
arrives with harness guidance addressed to whoever opened the pull request.
Under this skill that is never this session. So the prompt states what
`Non-goals` states: each pull request is its task session's to drive — a
failing check, a review finding or a conflict is that session's work. Landing
a merge-ready pull request, marking the wave, and closing the epic are this
session's work. A prompt naming only the wave's issue and pull request numbers
leaves the posture to whatever is still in context, which on a cheaper
orchestrator is nothing.

**Ten minutes, not two.** `undertake` checks in every two because its branch
goes stale while it waits and the merge that fixes that is cheap. Nothing here
decays that way: this backstop catches a dropped event and a dead session, the
worst case it bounds is one wave delayed by one interval, and a wave of five is
already holding five two-minute cadences of its own. A second-by-second watch
over the top of them is quota spent on nothing, and the constitution's
*Delegation* rule says whose money that is. In the fallback the subagent
lifecycle supplies the wake, and where the harness can hold no timer at all
the wave is read again whenever a result or a pull-request event next wakes
the session — said once, not claimed.

**A quiet task is what the backstop is for.** Three ways one goes quiet:

- Its session is no longer running while its pull request is open and unmerged.
- Its pull request has not moved across two check-ins while its session says it
  is running.
- **It has no pull request at all across two check-ins.** A session that died
  before `undertake`'s `Open the draft` leaves nothing to watch, which is why
  the first two clauses cannot see it — and left unwatched it is a task that is
  at sea for ever and a wave that never comes in.

None of the three is a verdict on its own: a session can be running and stuck,
a pull request can be legitimately waiting on a person, and a large task can
take two check-ins to reach its draft. Read the task's pull request and its
session before acting, and act at `Recover a session`.

6 — Land the pull request
-------------------------

Reached from `Watch the wave` on every wake, once for every task pull request
in the wave, and returns there.

**The landing gate is a read, not a judgement.** It follows `undertake`'s
`Ready is a gate, not a step`: take the reads in order, and the first one that
does not hold is the reason this pull request does not land.

1. **The pull request is not a draft.** `undertake` clears the draft at `Ready
   for review`; this skill never does.
2. **Its merge state is `clean`.** This is the value `undertake`'s `The
   milestone` reads, and only `clean` is a yes here. `behind`, `dirty`,
   `unstable`, and `unknown` belong to the task session or to a wait.
   `blocked` after the draft is clear means a required approval only a person
   can give; record that once on the epic in the task's muster-roll entry.
3. **No review thread is unresolved.** Use the thread read named by
   `review-cycle`'s reference for the active harness.
4. **No human action is owed.** The pull request carries neither the `human`
   label nor `pr-body`'s human-action notice.

A failed read produces one line in the task's muster-roll record and no merge.
A later wake that finds the same state stays silent. A change in state earns
the reads again.

When all four reads hold and the roll says `Landing: by hand`, report the
merge-ready pull request once and return without merging. That is the whole
opt-out.

When all four reads hold and the roll says `Landing: orchestrator`, squash
merge in the same turn. The repository is squash-only and uses the pull
request title as the squash subject, which is load-bearing for
release-please. No summary comes first, no permission is sought, and no turn
ends on an intention to merge later. This is a direct merge call, not GitHub
auto-merge.

7 — Recover a session
---------------------

Reached from `Watch the wave`, and it returns there.

- **Steer a running session**: interrupt it first, then send the correction.
  A message to a session mid-turn queues behind whatever that turn is doing,
  which is usually the thing being corrected.
- **A session is addressed by the name the agent listing gives it**, which is
  not the identifier the muster roll records. The reference file has the two
  calls and their order. A fleet member that the listing does not name cannot
  be steered at all, and is reopened instead.
- **Messaging is one way.** The session receives it and cannot answer, so the
  result of a correction is read from the pull request, never from the session.
- **Reopen a session that cannot be recovered**: archive it, and open a fresh
  one on the same task issue, pushing to the **same branch** rather than to one
  of its own. The branch is recorded twice already — in the claim comment
  `undertake` posted on the task issue, and as the head of the pull request if
  one is open — and either is read rather than guessed. Given that branch the
  replacement picks the work up where it was left: `pr`'s existing-PR check
  finds the open pull request rather than opening a second one, and the commits
  already pushed are on the branch it is handed.
- **A fallback implementor is recovered the same way, through the messaging it
  asks for help with.** A correction goes to the subagent's identifier; one
  the harness reports as failed, or as finished with no pull request across
  two check-ins, is relaunched on the **same branch** the claim comment
  records, and the replacement is posted to the epic like any other.
- **The replacement claims the task again, and that is correct.**
  `undertake`'s `Claim the issue` suppresses a second claim only for a session
  re-entering its own sequence, and reports a claim from any other session as a
  collision. The replacement is another session, so it does both — and the
  collision it reports is a true statement about the task, which now carries
  two claims because the first session is gone.
- **Post the replacement to the epic.** One comment naming the task, the
  session retired and the session that took over. The muster roll is what
  `Take the wave` reads at-sea status from, so a recovery nobody wrote down is
  a record pointing at an archived session — and the next watcher follows it.
- **A session that stopped to ask is a stop**, named under `Where it stops and
  waits`. The question cannot be read from here, so it cannot be answered from
  here.

8 — Close the epic
------------------

Reached from `Take the wave`, when no task issue of the epic is open.

Read every claim in the epic's `Summary` against the merged pull requests of
its task issues. Each claim must be delivered by at least one of those pull
requests. This is `epic`'s existing close test made mechanical: the task pull
requests are the evidence, and no open task count stands in for it.

When every claim is delivered and the roll says `Landing: orchestrator`,
post one comment listing the pull requests that landed, then close the epic
with `state_reason: completed`. When a claim is delivered by none of them,
post one comment that names the missing claim and leave the epic open. That
report-and-wait path is the only outcome here that asks a person for
anything.

When the roll says `Landing: by hand`, report that the epic is ready and leave
it open. In every outcome, cancel the backstop and drop every pull-request
subscription, so the check-ins end here.


Waves launch without confirmation
=================================

`epic` stops once, at `Agree the plan`, and what it agrees there is the whole
decomposition — the tasks, the edges, and therefore the waves. Asking again
before each wave asks the same question a second time, and a plan that has to
be re-agreed wave by wave was not agreed.

So the first wave and every wave after it launches unasked. `Post the muster
roll` is what goes up instead: the user sees five sessions start without having
been asked to approve them starting, and sees on the epic which task each is
on, which session is which, and what each is running. A record written as the
thing happens is worth more than a question answered before it.

This does not relax anything else. The stops below still stop, and nothing here
touches the constitution's own gates.


Where it stops and waits
========================

Five, and three of them are reports rather than questions.

- **An issue that is not an epic**, at `Read the epic`. A report: say which
  issue it is and which skill takes it — `undertake` for a task issue, `epic`
  for work not yet decomposed.
- **No wave to take**, at `Take the wave`. A report: every open task is blocked
  by something open, so name the issue that blocks and wait for it.
- **A session that stopped to ask**, at `Recover a session`. Name the task,
  its session and its pull request, and hand the question to the user. A
  fallback implementor's question is the other thing: it arrives through the
  messaging, is readable, and is answered on the advisor route. This stop
  covers the question that cannot be read — a web session that stopped, or a
  delivery that failed. Guessing at
  the answer is guessing at intent twice over — the constitution forbids it
  once, and this skill did not write the code being asked about.
- **The epic's graph disagreeing with its body about a blocker**, at `Take the
  wave`. The graph wins, so the wave is not in doubt; the body is wrong, and
  fixing it is `epic`'s `Fill in the epic` rather than an edit made in passing
  here.
- **A `Summary` claim that no merged task pull request delivers**, at `Close
  the epic`. Name the claim, leave the epic open, cancel the watch, and wait
  for a person to resolve the mismatch.

Everything else runs through. No permission is asked to open a session, to
comment on the epic, to subscribe to a pull request, to launch the next wave,
to merge a pull request whose landing gate holds, or to close an epic whose
`Summary` is delivered.


Non-goals
=========

- **Does not decompose.** The tasks, the edges and the waves are `epic`'s, and
  an epic whose plan is wrong is corrected there rather than worked around
  here.
- **Does not implement, drive, or answer a review.** Each task session does
  its own work through `undertake` and the round that skill runs. It fixes a
  failing check, answers a review finding, and resolves a conflict. The
  exception is the strong-model review `Open the sessions` requires of a
  fallback implementor's pull request: that round is the orchestrator's or
  the shared advisor's to run, because the rule exists precisely so the
  implementor does not review itself. Landing is narrower: a mechanical read
  followed by one squash-merge call.
- **Does not choose a model on the web route.** The task issue records one and
  this skill passes it on. Staying dumb is the point: the planner knew which
  task was a documentation edit, and this skill does not. In the fallback it
  applies the cheaper default `Open the sessions` states, and the bypass is
  the orchestrator's judgement to make.
- **Does not manage sibling branches.** It does not serialise their merges and
  it does not resolve a conflict between them. Landing one pull request moves
  the base; each sibling's `undertake` session brings that base into its own
  head through `Keep it current`.
- **Does not close the epic in `Landing: by hand` mode.** It reports the epic
  ready and stops there. The default `Landing: orchestrator` mode closes it
  only after `Close the epic` reads every `Summary` claim as delivered.
- **Does not fire on one issue, and takes nothing with it.** Undertaking a
  single task is the task session's own job, and running a fleet of one costs
  an epic, a muster roll and a watch to save nothing. The dispatch does not
  survive into that case either: `undertake`'s `Implement` has the session
  that claimed the issue write the code itself, and a dispatch there would
  only copy the session already on the work. Delegation here buys
  parallelism across task issues; there is none to buy in a fleet of one.
- **Does not sweep for epics.** It works the epic in hand. Reading the issue
  list for others to put to sea is `epic`'s manufacturing failure, one level up.
