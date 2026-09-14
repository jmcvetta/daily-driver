---
name: epic
description: >-
  This skill should be used whenever a piece of work is being broken into more
  than one issue, or an epic issue is being opened, read or corrected —
  including when the user says "/epic", "break this down", "this is too big
  for one PR", "split #142", "make an epic for this", or "which of these has
  to land first", and on Claude's own move from a request that will not fit
  one pull request to writing issues for it. It is also where `undertake`
  sends work too big for the one issue it takes in, and it fires on an attempt
  to undertake an epic, which carries no code. Supplies the two gates that
  decide whether there is an epic at all, what a task issue is and the model
  it records, the one stop where the plan is agreed before anything is
  written, and the shape of the epic body — the sequencing and the waves
  neither the sub-issue panel nor the dependency graph renders. The graph
  writes are `issue-deps`'. Not for taking a task issue to a pull request,
  which is `undertake`, and never fired on work that fits one.
---

# Epic planning

Work too big for one pull request becomes several task issues and one epic to
coordinate them. This skill is the order that happens in, the two gates that
decide whether it should happen at all, and what the epic body carries.

It is an orchestrator, in the same shape as `undertake` and `pr`: **it invokes,
it does not restate**. The graph writes are `issue-deps`', taking a task issue
to a pull request is `undertake`'s, and whether the plan is the user's to agree
is `judgement-call`'s. Where a step below names a rule one of those owns, it
names it as a pointer and cites the owner — a rule that acquires a second home
is one whose copy goes stale.

What this skill owns is the decomposition: what a task is, what an edge is for,
and what the epic body says that nothing else can render.

**The routes are per harness, and they live beside this file.** Every call the
steps below need is named in words here and resolved to a route there:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi,
[`references/codex.md`](references/codex.md) for Codex. Read the one for the
harness in use before `Size the work`, which is the first step with a route in
either table.

**Every step has a name, and the name is how it is cited.** The numbers order
the sequence and do nothing else: insert a step and all of them move, while a
name stays where it was put.
[`0005`](../../docs/notes/0005-steps-are-cited-by-name.md) is the decision and
`scripts/check-step-names.py` is what enforces it.


The sequence
============

| # | Step | Owner |
| - | ---- | ----- |
| 0 | `Size the work` | this skill |
| 1 | `Draft the plan` | this skill |
| 2 | `Agree the plan` | this skill, `judgement-call` |
| 3 | `Open the issues` | this skill, `undertake`, `issue-labels` |
| 4 | `Write the graph` | `issue-deps` |
| 5 | `Fill in the epic` | this skill |
| 6 | `Hand off` | `undertake` |

0 — Size the work
-----------------

An epic has to earn itself. One issue is the default, and it stays the default
unless **both** gates below open. Where either closes, say which one and carry
on as ordinary work — `undertake` where there is an issue or an invocation,
plain work where there is neither.

**Gate one: more than one pull request.** Would the whole change land as one
diff a reviewer reads in one sitting? Where it would, there is nothing to
coordinate. Size is measured in reviewable diff, never in hours or in files.

**Gate two: two parts that can merge separately.** Take each candidate part and
ask one question of it:

> Merge this part alone, and nothing else. Is the repository better off, and is
> CI still green?

A part answering no to either half is not a task. Where fewer than two parts
answer yes, the work is one issue however large it is: an epic over parts that
cannot merge separately is a table of contents. It costs everyone the issues
and buys a reader nothing.

An issue already in hand is sized the same way, and the answer is the same
answer. Where the gates close on it, it stays one issue and nothing is opened.

1 — Draft the plan
------------------

Nothing reaches GitHub here. The plan is drafted, and then it is agreed.

**A task is one pull request.** Where a candidate task needs two, split it
again rather than making it a second epic. This skill does not nest: a graph
two levels deep is read by nobody, and the second level is always a split
somebody declined to make.

**Each task issue records what was asked and no more**, the way `undertake`'s
`Open the issue` writes one. Scope invented to round out a plan is scope every
pull request is then measured against. A plan padded to look thorough is this
skill's manufacturing failure, and it is the same instinct `issue-deps` names
for edges.

**Cut for parallelism, before there is a graph to read it off.** How much of
the work can run abreast is decided here, when the tasks are defined — not
afterwards, by whatever shape the edges happen to take. Choose the cut lines
that put as much of the work as possible in parallel: separate the parts that
touch different files, and do not order two tasks that have no reason to be
ordered.

Two tasks touching one file are not blocked on each other. That is a merge
conflict, and a merge conflict is cheap — but a cut line that avoids the shared
file is better than one that does not, because the conflict still costs
somebody a resolution. Splitting first and deriving the waves from the graph
that falls out leaves the parallelism to chance, and it is the failure this
rule names.

**The order is edges, and the default is no edge.** Write a blocked-by edge
only where one task's code cannot be written until the other has landed — a
function that does not exist yet, a schema the second task reads. Never as
prose in the epic body: the edge is the record, and `issue-deps` owns what an
edge means and what it must not be used to record.

**Parallel is then the absence of an edge**, and nothing has to be written for
it to be true. What the epic body carries is the *reading* of it, under
`The epic body` below.

**Each task records the model that should undertake it.** Sizing a task is the
moment it is known whether the work is a documentation edit or a schema
migration, and that judgement is otherwise thrown away: `embark` dispatches
one ship per task, and on the web-session route deliberately does not choose —
the line binds there. On a harness running `embark`'s subagent fallback the
line is advisory: the fallback's cheaper implementation default applies, and
the orchestrator reads the line before dispatching. Pick the lightest model
that can do the task well — the constitution's *Delegation* rule is that
quota is the user's money, and it cuts both ways, because a schema migration
on a small model costs more than it saves.

**The form is exact, because a skill parses it rather than a person.** The last
line of the task issue body, and nothing after it:

```
Model: claude-sonnet-5
```

The identifier must be one the harness's session client accepts. The reference
file for the harness in use names them, and it is read rather than recalled.
**Where no valid identifier can be named, write no line at all**: a missing
line is a working default in both routes — the web session inherits the
orchestrator's model, and `embark`'s subagent fallback applies its cheaper
implementation default — and a session opened on a model that does not exist
is not.

**Reasoning effort cannot be recorded.** The session client takes a model and
has no effort parameter — effort is session configuration rather than a
dispatch argument — so an `Effort:` line beside the model would be read by
nothing. Do not write one.

2 — Agree the plan
------------------

The one stop. Put the plan in the reply — each task as a title, a line, and the
model it suggests, each edge as what it waits on, the gates' answer from
`Size the work`, and, where an existing issue is to become the epic, which
issue that is and that its body is replaced — and write nothing until the user
agrees.

It clears `judgement-call`'s gate on scope. A decomposition is a statement of
scope: it says what the pieces are and what done means for each, and craft does
not pick one split over another.

The edges are agreed here too, and not because `issue-deps` asks for them — it
writes an edge from evidence and reports the write. They are agreed because
they **are** the plan: an edge says which task waits on which, so the order of
the work is as much a statement of scope as the split is.

**One agreement covers the whole plan**, edges included. `Write the graph`
writes them and reports each one, and asks nothing a second time.

3 — Open the issues
-------------------

**Search before writing**, for the reason `undertake`'s `Open the issue` gives:
a change described in a prompt has often been described in an issue already,
and a second issue for it splits the trail in two.

Each task's body records what was asked and ends with its `Model` line, both
settled at `Draft the plan`.

Where an issue already describes the whole change, **that issue becomes the
epic**. Do not open a second one beside it: rewrite its body the way a new
epic's is written here, and the rest of the sequence then runs unchanged —
`Write the graph` attaches the children, and `Fill in the epic` adds
`Sequencing`.

**That rewrite replaces the body rather than adding to it**, so the prose the
user wrote is gone from the issue the moment it lands. Two things make that
safe, and neither is optional. `Agree the plan` names the issue and says its
body is replaced, so the conversion is agreed rather than done to somebody.
And nothing in the original is dropped: what it says about the whole change
becomes `Summary` and `Justification`, and what it says about one part goes
into that part's task issue, which is where the person doing the work will
read it.

The epic first, then the tasks, because a task names the epic as its parent and
the parent must exist to be named. The epic's body at this point is `Summary`
and `Justification`, and stops there: `Sequencing` is made of issue numbers
that do not exist yet, which is why `Fill in the epic` is a step of its own.

**Every issue this step writes carries a label**, and `issue-labels` supplies
them. The epic gets `epic`, which is the one word that stops `undertake`
starting on it; each task gets `task`, `bug`, `research` or `human`, whichever
it is. A child whose work is a person's is written and sequenced like any
other, and `human` is what tells `embark` to leave it for the person rather
than open a session on it.
An issue converted into the epic is **relabelled** rather than labelled: it
carried something before, and two of the six on one issue is a stop in its
own right. Both harnesses make that swap awkward, in opposite ways, and the
reference file for the one in use says how: a write that *adds* needs the
remove in the same call, and a write that *replaces* needs the issue's
current labels read first, or the stock and bot-owned ones go with the swap.

No permission is asked here. It was asked once at `Agree the plan`, and asking
again per issue is the same question eight times.

4 — Write the graph
-------------------

Two relationships, and `issue-deps` picks a client for each. They are not
always the same client, and on a web worker they are not.

- **Parent.** Every task is a sub-issue of the epic. Where the harness's issue
  client sets the parent as the task is created, that write already happened at
  `Open the issues`.
- **Blocked-by.** Only the edges `Draft the plan` named.

**An epic's children are not its blockers.** `issue-deps` says why:
decomposition and *must close first* are different claims. Do not write the
second because you wrote the first.

Verify from the other end, which `issue-deps` requires and explains — the write
response is the issue you modified, so it confirms nothing.

5 — Fill in the epic
--------------------

Replace the epic's body with the whole of `The epic body`, now that every task
has a number to put in it.

6 — Hand off
------------

Every task whose blockers are closed can start now, each in its own session,
each through `undertake`. Name them, rather than leaving the reader to derive
the list the first time.

**Putting that wave to sea is `embark`'s**: one ship per task — a session
where the harness opens web sessions, its subagent fallback where it cannot —
watched to merge, and the next wave after it. The list named here is what it
takes in.

**The epic is never undertaken**, which is the stop of that name under
`Where it stops and waits`. It carries no code; the tasks named above are what
a session takes.

**No pull request closes the epic.** A pull request implements one task, and
that task is the issue its body closes. Closing a sub-issue does not close its
parent — GitHub has no such rule — so the epic is closed by hand, and the test
is its own `Summary`: the epic closes when what that section describes is true
of the repository, which is usually but not always the moment the last task
merges.


The epic body
=============

Three sections, and no fourth. `Summary` and `Justification` are written at
`Open the issues`; `Sequencing` waits for `Fill in the epic`, because it is
made of issue numbers that do not exist until the tasks are open.

Summary
-------

What is to be changed: how the software behaves differently once the epic is
finished. Concise, and about the end state rather than the route to it — the
tasks are listed under `Sequencing`, and repeating them here is a second list
to keep current.

It is also the test `Hand off` closes the epic against.

Justification
-------------

Why this is being done. **Very** concise — a sentence or two. An epic that
needs a page of justification is either not agreed yet, in which case
`Agree the plan` has not finished, or it is carrying a design discussion that
belongs in a note under `docs/`.

Sequencing
----------

What order the tasks can run in, and which of them run in parallel. One
heading per wave, naming what the wave waits on, and under it the tasks with a
line each:

```markdown
### Wave 1 — no blockers · done
- #143 — Parse the manifest.
- #147 — Document the format. Touches no file #143 does.

### Wave 2 — after #143 · in progress
- #144 — Validate against the schema.

### Wave 3 — after #144
- #145 — Report a validation failure.
```

Read the headings, not the lines. **The heading names what the wave waits on**,
and the state after it — `done`, `in progress` — belongs to the wave rather
than to any task inside it. A line says only what the graph cannot: #147's says
why it is safe to run abreast of #143, and #144's says nothing at all, because
its wait is already in its heading and repeating it on the line is the
duplicate state `What the body leaves out` forbids.

A wave is a batch that runs together: **nothing inside one heading waits on
anything else inside it**, so everything in a wave runs at the same time, in
its own session. That is what answers "which of these can be worked in
parallel", and `Draft the plan` is where it was actually decided — this section
records the answer rather than producing it.

A task with no blocker at all may still sit in a later wave, as a scheduling
choice rather than a dependency — and then **its line has to say so**. Left
unsaid, its position reads as a wait, and the body has made a *must close
first* claim the graph does not carry.

**The waves are a rendering of the graph, and the graph wins.** Where the two
disagree the body is wrong and is fixed in the same turn. That is `issue-deps`'
own verification step — does the structured graph match what the prose says —
and an epic body is the largest prose claim about a graph this toolkit writes.

What the body leaves out
------------------------

- **No implementation detail.** It belongs in each task's own issue, where the
  person doing the work is reading.
- **No checklist of the tasks.** The sub-issue panel renders progress from the
  graph, for free and always correctly, and a hand-kept copy beside it rots.
- **No blocker stated only in prose.** A `blocked-by` edge is the record; a
  line saying "waits on #143" beside it is duplicate state, and `issue-deps`
  says to delete that line rather than maintain it. The wave headings above are
  the reading of the graph, not a second copy of it.


Where it stops and waits
========================

Four, and only the first is routine.

- **The plan**, at `Agree the plan`. One stop by design, covering the scope
  question and every edge at once.
- **A request too vague to decompose.** The constitution forbids guessing at
  intent, and a decomposition guesses harder than an issue does: it invents the
  boundaries, and then every pull request is measured against boundaries nobody
  chose. Ask what the whole change is for, and do not draft a plan around the
  answer you would have preferred.
- **A gate closing at `Size the work`.** A report rather than a question: say
  which gate closed, and carry on as ordinary work.
- **An epic handed over to be undertaken.** `undertake` stops at
  `Read the issue and its edges` and delegates the wording here, and this is
  the wording: an epic carries no code, so there is no branch to cut and no
  pull request to open. The sequence does not run on it either — the work is
  already decomposed, and `Size the work` has nothing left to size. Say which
  issue is the epic, name the tasks whose blockers are closed, and undertake
  one of those. An epic whose body or graph is wrong is an edit at
  `Fill in the epic` or `Write the graph`, not a reason to plan it again.


Non-goals
=========

- **Does not implement anything.** It writes issues, edges and one body.
  `undertake` takes each task from there.
- **Does not fire on work that fits one pull request.** That is `Size the
  work`'s first gate, and it is first for this reason. An epic over a two-file
  change costs a reader more than the change does.
- **Does not nest.** A task too big for one pull request is split again, never
  promoted to a second epic.
- **Does not keep a second copy of what the panel shows.** A wave heading
  carries its own state, because a wave is not something the sub-issue panel
  knows about. A checkbox beside each task is, and it rots.
- **Does not close a task.** Merging its pull request does that. The epic is
  closed by hand instead, against its `Summary` — see `Hand off`.
- **Does not sweep the issue list.** An epic is drafted for the work in hand.
  Reading through open issues looking for a set that could be grouped under one
  is `issue-deps`' manufacturing failure, one level up.
