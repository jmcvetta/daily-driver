---
name: issue-deps
description: >-
  This skill should be used whenever a relationship between GitHub issues is
  being recorded, read, or relied upon — one issue blocking another, a
  sub-issue or parent, or which pull request closes an issue. It fires on the
  literal "/issue-deps", on natural phrasings ("this is blocked by #123",
  "what's blocking this", "make it a sub-issue of the epic"), on noticing
  while planning or writing a PR body that other work must land first, and
  before recording or reading a blocked-by, sub-issue or parent edge, or
  writing a `Closes #123` line in a pull request body. Supplies the client
  selection rules and the rule that an edge the evidence supports is written
  and reported rather than asked about.
---

# Issue relationships

Three relationships, one graph. The available clients differ by harness and
environment. The wrong client can answer with only a count where the question
was *which*, or omit a write path without saying that another client has one.
The active harness reference therefore owns both the client probe and every
executable route.

The one thing that is *written* as prose is the `Closes #123` line in a pull
request body. Treat the graph as the artifact and that line as one unvalidated
writer into it.

**The exact form is per harness, and it lives beside this file.** Every
operation below is named in words here and resolved to a call there:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi,
[`references/codex.md`](references/codex.md) for Codex. Read only the one for
the harness in use, before the first call.


Client selection
================

Probe, do not assume. Follow the active harness reference's ordered probe and
use the first client whose version, authentication and capabilities all hold.
A client that can read only counts cannot answer which issues participate in a
relationship. A client that cannot write must not be tried as if it could.
Report an unavailable operation plainly rather than discovering the limitation
through a failed write.


Write from evidence; report every write
=======================================

The failure mode of this skill is **inventing relationships**. An agent handed
a job feels obliged to produce output, and this job's output is edges.

A wrong edge is still worse than a missing one, and the reason is **silence**:
it blocks work nobody knows is blocked, and nobody thinks to look for a
relationship they did not create. Silence is cured by announcing the write,
not by asking before it. An edge is outward-facing — it lands in a tracker
other people read — and that is what the report answers; what it is not is
expensive to take back, because one `remove` undoes it.

So: state the evidence, name the edge it implies, **write it**, and report the
write.

- **Report every write, prominently.** The edge, both ends by repository and
  number, and the evidence it came from. The write is verified from the
  blocking side anyway — `The traps` says why — so the fact is in hand before
  the report is written.
- **Reading is free**, and needs neither a confirmation nor a report.
- **Two things stop a write, and only two.** A **contradiction** — the edge
  disagrees with something the user has said — and a **plan not yet agreed**:
  inside `epic`, every edge waits for `Agree the plan`, the one stop that step
  is, whether it was drafted there or noticed while drafting. Name what is
  wrong, or what the edge is waiting on, and ask. Nothing else here waits.

**The evidence test is now the whole guard**, so it is stated exactly. It
covers **every inferred edge** — blocked-by, sub-issue and parent alike, which
is the reach the confirmation had. Both of these must hold before one is
written:

- **The relationship was discovered in the work in hand** — while planning a
  change, or while writing a PR body and realising it cannot merge first. Not
  while reading the issue list for edges to add.
- **The evidence is a statement about the issues, of the kind the edge
  claims.** The two kinds are different claims, so the evidence is different
  too, and evidence for one is never evidence for the other:
  - **Blocked-by** says *this must close first*, so the evidence is about the
    code. One issue reads a function the other adds; one issue's fix is in a
    file the other deletes.
  - **Sub-issue or parent** says *this is part of that*, so the evidence is
    about scope. The parent states scope the child is one piece of, and the
    child closes without the parent closing.

  A shared subject is evidence of neither, and neither is a shared label,
  milestone or author.

**An edge that is given rather than inferred does not go to the test**, and
there is nothing there for it to weigh. `epic` writes the parent edges and the
blocked-by edges of a decomposition the user has already agreed, and
`undertake` writes a `Closes #123` line the assignment states. The test is for
an edge nobody asked for, which is the only kind that can be invented.

A sweep of the issue list looking for edges to add is the manufacturing
failure, not the skill working. The evidence test is what stops an edge between
two issues that merely share a subject.


What is a blocker
=================

An edge means **another issue must close first**. It is not a place to record:

- A dependency on a person, a purchase, or a decision. There is no issue to
  point at, and inventing one makes the graph say something false about what
  unblocks the work.
- A pull request. The API refuses it at both ends of both graphs — *"Source
  issue may only be an issue"*, *"Target issue may only be an issue"*, *"Parent
  may only be an issue"*, *"Sub issue may only be an issue"*.

**A pull request that must wait on another pull request has nowhere structural
to record it.** That dependency belongs on the issues the two PRs implement,
where it is an ordinary edge and where it outlives both PRs being merged or
abandoned. In the PR itself it stays prose, and prose is all it can be.


The full-graph client
=====================

Where the active reference supplies a client that reads and writes the whole
graph, use its exact argument rules. Issue relationships name an issue number
or URL, never a database identifier. A removal that takes no other issue must
not be given one. State an edge from either end only where the client supports
that direction.

Refusals must exit non-zero and leave the graph unchanged. Read a command's
status before piping its output. A read against a pull request can return the
same empty shape as an issue with no edges, so verify the target is an issue
before believing an empty result.


The fallback client
===================

One environment has a bundled fallback for blocked-by and blocking edges.
The active reference gives its exact path and invocation. Never replace that
path with one relative to the user's project: an unrelated project script can
then run instead of the skill's client.

The fallback accepts issue numbers, owner-and-repository references, and
GitHub issue URLs. It states an edge from the blocked side because that is the
only direction its transport accepts. It reaches blocked-by and blocking only.
Where no available client reaches sub-issues or closing pull requests, report
that limit rather than treating summary counts as the requested answer.

Cross-repository blockers are ordinary. The blocker's repository only has to
be readable by the credential; nothing needs write access there.


Sub-issues
==========

Use the active reference's first client that supports parent and child edges,
including cross-repository edges. Where no available client has that write
path, report the limitation rather than inventing another transport.

Parent/child is *decomposition* — this issue is part of that one — and is a
different claim from *this must close first*. An epic's children are not
automatically its blockers, and saying so in edges would be inventing
relationships.

**The `epic` label and the parent edge are not the same statement**, and both
are wanted. The label says an issue coordinates others, which stops `undertake`
starting on it; the edge says *which* children it has. `epic-child` is the
derived list marker for a confirmed direct child of an epic. After creating,
changing, removing, or reading a parent relationship, verify the child's
direct parent, then invoke `issue-labels` to reconcile that marker. The label
skill owns its write rules: preserve it when the graph read fails, and never
write an edge to justify it. An epic with no children is a label with nothing
behind it.


Which PR closes an issue
========================

Use the active reference's structured closing-relationship read. The issue
timeline renders *"this PR closed it"* and *"this PR mentioned it"* identically,
so a timeline or unstructured REST answer is wrong rather than merely missing.

This is the skill's verification step, and it is worth running whenever an
issue's body claims a relationship: **does the structured graph match what the
prose says?** The `Closes #123` convention writes into this graph as an
unvalidated string, with no way to notice when it is wrong.


The traps, all of them silent
=============================

Every failure mode here can return success. That makes verification mandatory.

- **A relationship read against a pull request can look exactly like an issue
  with no edges.** Check the target kind before believing an empty answer.
- **A database identifier is not an issue number.** Clients that accept raw
  identifiers can create an edge to an unrelated issue without failing.
- **A write response can identify only the issue modified.** Verify from the
  other end; a wrong edge otherwise appears as silence.
- **A pipe can replace the client's exit status.** Check the write before
  piping its output.
- **Print the repository on both ends when reporting an edge.** A bare `#2853`
  reads as local and need not be.

An edge to a closed issue stops blocking without anyone editing anything —
which is the argument for edges over a `⛔ BLOCKED ON #189` banner, and the
reason a banner should be deleted once the edge exists.


When prose stays
================

An edge is binary and carries no reason. Keep a note in the body when it says
something the edge cannot: that the block covers only part of the issue, or
which of a blocker's several defects actually bite. Delete the line whose whole
content is "blocked on #199" — that is duplicate state, and it will rot.


Expiry
======

The bundled fallback exists for an environment whose native clients cannot
reach blocked-by and blocking edges. Delete it when every supported environment
has a native client with those read and write capabilities. Keep this skill:
the relationship policy is independent of the transport.

Background, endpoints and the probe tables:
[`jmcvetta/career`, `docs/issue-dependencies.md`](https://github.com/jmcvetta/career/blob/master/docs/issue-dependencies.md).
