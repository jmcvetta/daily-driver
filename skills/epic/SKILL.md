---
name: epic
description: >-
  Use for `/epic` when work is broken into more than one issue, or an epic
  issue is opened, read, or corrected, including work too big for one pull
  request and an attempt to undertake an epic, which carries no code. Supplies
  the fit gates, assignable stories and model class, the plan-agreement gate,
  and the epic outcome and scheduling constraints. The GitHub graph owns
  membership and prerequisites. Graph writes are `issue-deps`'. Not for taking one
  child issue to a pull request (`undertake`), and never for work that fits one
  issue.
---

# Epic planning

Work too big for one pull request becomes several child issues and one epic to
coordinate them. This skill is the order that happens in, the two gates that
decide whether it should happen at all, and what the epic body carries.

This skill owns decomposition and the epic body. It invokes `issue-deps` for
graph writes, `undertake` for delivery, and `judgement-call` for scope agreement.

**The routes are per harness, and they live beside this file.** Every call the
steps below need is named in words here and resolved to a route there:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi,
[`references/codex.md`](references/codex.md) for Codex. Read the one for the
harness in use before `Size the work`, which is the first step with a route in
either table.

**Cite steps by their stable names**, not their sequence numbers.

Discovery and specification-backed delivery
===========================================

When research and a collaboratively settled specification must precede
decomposition, open the coordinating issue as `discovery`, not an `epic`.
Keep that issue number, comments and parent/child lineage throughout. Its body
states the intended outcome, open research, interactive specification child,
and sequencing; it does not pretend implementation is settled. The parent
may have eligible `research` children and at most one active interactive
`specification` child. Do not open implementation tasks before the operator
has approved and merged the specification. `embark` runs eligible research
only and returns here when it is exhausted; it never closes the discovery on
child count or dispatches the interactive specification.

After operator approval and merge to `master`, publish one stable, identifiable
parent record (for example, a uniquely linked parent comment) containing the
canonical document path, exact merged commit and evidence of operator approval.
Do not overwrite it on amendment. With separately agreed decomposition, each
implementation task references that particular record and allocates stable
requirement IDs and exclusions, plus the map, verification and class required
by `issue-body`. Resolve the record and read the document at its exact commit;
verify each ID, allocation, exclusions and agreement before dispatch. Missing,
changed, ambiguous or inaccessible records cannot authorize work: report the
gap and return it to `epic`, never select the latest revision. Existing tasks
that pin their own path and SHA remain valid under that original contract.
Write and verify the graph. The discovery label prohibits dispatch of staged
implementation until all gates pass and the parent is atomically promoted.

If the agreed outcome fits one PR, convert the same parent to a single
specification-backed `task` only with scope agreement, rather than creating an
artificial epic. If evidence supports not proceeding, record it and close the
parent as not planned.

For a substantive amendment, atomically demote the same `epic` to `discovery`
before affected work proceeds. Preserve all existing issues, edges, allocations
and provenance. Identify and pause only affected implementation; independent
eligible implementation already in progress may continue against its existing
contract, but discovery dispatch never starts a staged implementation task.
Add needed research and one active interactive amendment specification child.
`specification` owns renewed operator agreement, review and operator merge.
After merge, create a distinct publication record and reconcile affected
allocations and execution contracts with original-user authority for material
changes. In-progress work retains its original binding until an authorized
transition. Recheck references, graph, readiness and coverage before atomic
re-promotion. An implementation PR must not silently amend its specification.


The sequence
============

| # | Step | Owner |
| - | ---- | ----- |
| 0 | `Size the work` | this skill |
| 1 | `Draft the plan` | this skill |
| 2 | `Agree the plan` | this skill, `judgement-call` |
| 3 | `Open the issues` | this skill, `undertake`, `issue-labels`, `issue-body` |
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

Nothing reaches GitHub here. The plan is drafted, and then it is agreed.

**Name the first useful delivery before independent improvements.** Describe the
smallest complete user outcome and the functional and safety prerequisites it
needs. List independent improvements separately, with their own useful outcome.
This is a scope distinction, not an automatic milestone or child issue: use the
two existing epic gates below, and keep necessary same-PR work together.

The first delivery is not a license to omit accepted requirements. Preserve
every explicit acceptance criterion. If a later request adds scope, explain
whether it moves the first useful delivery or adds an independently useful
outcome. Use `Agree the plan` only for an unresolved scope choice; an explicit
informed choice stands. Do not invent estimates, keep asking, or open follow-up
issues automatically.

**Prove the route before dependent investment.** Identify the uncertain
integration assumption that could invalidate the implementation approach.
Plan the smallest safe, bounded proof of the actual relevant integration and
authentication path before dependent machinery or paid provisioning. Startup
or health checks alone do not prove integration. The proof may be the first
action in one task; it is not automatically a research issue. If a proof input
is unavailable, report that exact gap and continue unrelated safe work.

**Keep task boundaries outcome-based.** File groups, activity names, or
changing from implementation to verification do not make independent tasks.
Keep work that must land together in one issue; preserve genuinely independent
infrastructure, documentation, research, and parallel outcomes. A verification
checkpoint or human prerequisite is not a blocked-by edge.

**For deployment work, plan continuity before provisioning.** Before the
first paid provisioning or sensitive state commit, identify authoritative
configuration and state locations, protection for sensitive provider-returned
state, recovery needs, and a cross-session resume path. Preserve artifact
identity and reusable nonsecret inputs without copying broad credential
stores. Include the approved host lifecycle in acceptance; session shutdown
alone does not authorize teardown. Reuse supported state/security tools. Do
not prescribe encrypted Git state universally, add a platform, retain
unapproved billable resources, or bypass production, destructive-operation, or
spending approvals.

These checks add no approval step or universal checklist. Scope agreement
remains `Agree the plan`; true dependency edges remain `issue-deps`.

1 — Draft the plan
------------------


**Membership is not assignability.** Link truthful children under the agreed
plan even when their handoff is not ready. Before dispatch, an assignable
story has exactly one agent-eligible kind (`task`, `research` or `bug`),
passes its own `issue-body` readiness test and carries one valid `## Model
class` section with rationale. Missing or invalid metadata never defaults to
`routine`. `issue-body` owns the test and `embark` applies it; research and
bug stories retain their own contracts. A parent edge, marker or kind alone
proves no readiness. Open blockers delay dispatch, not membership. Neither a
GitHub assignee nor an available concrete model is required during planning.

For an implementation epic, dispatchable stories exclude `proposal`,
`specification`, `human` and nested parent issues. The closed interactive
specification and research lineage remains attached after promotion; it is not
a dispatch candidate or a planning defect. A discovery's active specification
child is likewise a valid parent member, not a dispatchable story.

Each story records what was asked and no more. Scope invented to round out a
plan is scope every pull request is then measured against. A plan padded to
look thorough is this skill's manufacturing failure, and it is the same
instinct `issue-deps` names for edges.

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

**Parallel is then the absence of an edge**, subject to explicit scheduling
constraints the graph cannot express, such as global serial execution or a
spending limit. Record those constraints in the epic, never as false blockers.


2 — Agree the plan
------------------

It clears `judgement-call`'s gate on scope. Every story entry states its required
model class and short rationale. Each edge states what it waits on, and the
plan names any existing issue that becomes the epic. Nothing is written until
the user agrees.

A decomposition states scope: its pieces and what done means for each.

The edges are agreed here too, and not because `issue-deps` asks for them — it
writes an edge from evidence and reports the write. They are agreed because
they **are** the plan: an edge says which task waits on which, so the order of
the work is as much a statement of scope as the split is.

**One agreement covers the whole plan**, edges included. `Write the graph`
writes them and reports the operation without asking a second time.

3 — Open the issues
-------------------

**Search before writing**, for the reason `undertake`'s `Open the issue` gives:
a change described in a prompt has often been described in an issue already,
and a second issue for it splits the trail in two.

Each child body follows its kind's `issue-body` contract. Read reused issues
before changing them. Resolve repository-answerable gaps through `issue`;
preserve valid requirements, evidence and provenance, and follow
`issue-labels`' kind-conflict rules. Leave an already-ready story unchanged.
Do not relabel a kind or invent scope to fit the epic. If a required decision
or prerequisite is unavailable, report the exact gap, retain truthful
membership, and continue independent preparation. Do not present the child as
ready or dispatch it until its own test passes. Replacement issues need the
applicable scope agreement.

Where an issue already describes the whole change, **that issue becomes the
epic**. Do not open a second one beside it: rewrite its body the way a new
epic's is written here, and the rest of the sequence then runs unchanged —
`Write the graph` attaches the children, and `Fill in the epic` records constraints.

**That rewrite replaces the body rather than adding to it**, so the prose the
user wrote is gone from the issue the moment it lands. Two things make that
safe, and neither is optional. `Agree the plan` names the issue and says its
body is replaced, so the conversion is agreed rather than done to somebody.
And nothing in the original is dropped: what it says about the whole change
becomes `Human brief` and `Justification`, and what it says about one part goes
into that part's child issue, which is where its owner will read it.

The epic first, then the children, because each child names the epic as its
parent and the parent must exist to be named. Its body states the outcome,
justification and applicable scheduling constraints.

**Every issue this step writes carries one issue kind.** Select each child's
kind under `issue-labels`. If a create call also sets a parent, apply
`issue-deps`' membership evidence and plan agreement, then verify the edge and
reconcile `story`. The marker supplements the kind; it never replaces one.

When this step creates a new epic, report its link and the `epic` label under
[`issue`'s reporting rule](../issue/SKILL.md#reporting-a-newly-opened-issue).

After each child is created, report its link, its kind label, and the exact
class from its `Model class` section. Apply
[`issue`'s reporting rule](../issue/SKILL.md#reporting-a-newly-opened-issue)
to each child. Do not report the epic's label or another child's class as its
own.

An issue converted into the epic is **relabelled** rather than labelled: it
carried something before, and two of the eight kinds on one issue is a stop in
its own right. Both harnesses make that swap awkward, in opposite ways, and the
reference file for the one in use says how: an additive write needs the remove
in the same call, and a replacement write needs the issue's current labels
read first, or stock, bot-owned, and supplemental labels go with the swap.

No permission is asked here. It was asked once at `Agree the plan`, and asking
again per issue is the same question eight times.

4 — Write the graph
-------------------

Two relationships, and `issue-deps` picks a client for each. They are not
always the same client, and on a web worker they are not.

- **Parent.** Write each supported child relationship under `issue-deps`.
  Where creation already set the parent, verify it; otherwise write it here.
  Verify from the opposite end and reconcile `story`, even for an unready
  child.
- **Blocked-by.** Only the edges `Draft the plan` named.

**An epic's children are not its blockers.** `issue-deps` says why:
decomposition and *must close first* are different claims. Do not write the
second because you wrote the first.

Verify from the other end, which `issue-deps` requires and explains — the write
response is the issue you modified, so it confirms nothing.

5 — Fill in the epic
--------------------

Ensure the epic body states the outcome, justification and any scheduling
constraints. Report each child's readiness defects precisely; do not present
an unready child as dispatchable. Do not maintain a copy of graph membership
or status in the body.

6 — Hand off
------------

Derive eligible stories from the current graph and apply the recorded scheduling
constraints. Name the currently runnable set as a handoff, not a maintained
list. `embark` dispatches and watches it, then reads the graph again.

**The epic is never undertaken**, which is the stop of that name under
`Where it stops and waits`. It carries no code; the child issues named above
are what a session takes.

**No single child result closes the epic.** Each completes one story — by pull
request, or by an evidenced answer for research; none closes the epic merely
by closing. When the fleet runs through `embark`,
its `Close the epic` step checks the coordinated outcome against the children.
Without an embarked fleet, a person applies the same test.



The epic body
=============

The body states the human outcome, justification and any constraints that the
graph cannot express. It need not maintain waves or status. Preserve existing
historical bodies; do not migrate them in bulk.

Above the body, a **ballad quatrain**: four lines, the second and fourth
rhyming, each italicised as [`HAIKU.md`](../../HAIKU.md) shows. Retain
`provenance` attribution on each body write.

Human brief
-----------

What is to be changed: how the software behaves differently once the epic is
finished. Be concise and describe the end state, not a duplicate task list.

State the observable coordinated outcome and the evidence needed to establish
it. `embark`'s `Close the epic` checks that outcome; closed children alone and
inconclusive research do not establish delivery. A canceled child counts only
when the accepted condition explicitly permits it.

Where the epic has nontrivial components, flow, state, or data movement,
this brief should include one Mermaid diagram
that reveals that structure. The diagram is optional, not a quota: omit it
when prose is clearer or the structure is trivial. A diagram replaces prose
that would otherwise explain the same structure — never acceptance criteria,
never an exact contract, and never the dependency graph, which stays
authoritative for execution ordering. Where a diagram and the text disagree,
the text wins and the diagram is corrected in the same turn. No decorative
or duplicate diagrams, no progress checklists, and no second hand-maintained
dependency record.

Justification
-------------

Why this is being done. **Very** concise — a sentence or two. An epic that
needs a page of justification is either not agreed yet, in which case
`Agree the plan` has not finished, or it is carrying a design discussion that
belongs in a note under `docs/`.

Scheduling constraints
----------------------

Record only agreed constraints not represented by the graph, such as a global
limit of one active implementation or a spending ceiling. Enforce them even
when the graph has independent runnable children. Parent and blocked-by edges
remain authoritative for membership and prerequisites; never invent an edge
to represent a resource or scheduling limit. Derive eligibility from the
current graph, rather than maintaining wave lists or wave status. Historical
wave renderings are readable but are not authoritative duplicate state.


Where it stops and waits
========================

- Plan agreement and edges: `Agree the plan`.
- Request too vague to decompose: ask for the intended outcome before drafting.
- Sizing gate closes: `Size the work`.
- Epic presented to `undertake`: name the epic and eligible children; undertake
  a child instead. Correct its body or graph at `Fill in the epic` or
  `Write the graph` without decomposing it again.


Non-goals
=========

- **Does not implement anything.** It writes issues, edges and one body.
  `undertake` takes each task from there.
- **Does not fire on work that fits one pull request.** That is `Size the
  work`'s first gate, and it is first for this reason. An epic over a two-file
  change costs a reader more than the change does.
- **Does not nest.** A story too big for one pull request is split again, never
  promoted to a second epic.
- **Does not keep a second copy of graph membership or status.** Derive it
  from the sub-issue and dependency graph.
- **Does not close a task.** Merging its pull request does that. `embark`
  closes an embarked epic at `Close the epic`, against its `Human brief`; without
  a fleet, a person applies the same test.
- **Does not sweep the issue list.** An epic is drafted for the work in hand.
  Reading through open issues looking for a set that could be grouped under one
  is `issue-deps`' manufacturing failure, one level up.
