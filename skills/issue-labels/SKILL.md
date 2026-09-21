---
name: issue-labels
description: >-
  This skill should be used whenever a GitHub issue is being labelled, or a
  label on one is being read as a statement about the work — including when
  the user says "/issue-labels", "label this issue", "what label does this
  get?", "is this an epic or a task?", "that label is wrong", "which issues
  are ready for an agent?", and including any call Claude makes on its own
  initiative that sets a label on an issue. It fires too whenever `undertake`
  opens an issue or reads one it is about to start on. Supplies the six issue
  kinds and the supplemental epic-child marker, including their write rules.
  The kind decides readiness. Not for pull request labels or graph writes,
  which are `issue-deps`'.
---

# Issue labels

A label is read by a person scanning a list and by an agent deciding whether
to start. Six issue-kind labels answer one question:

> **What kind of issue is this, and is it ready for an agent to work
> unattended?**

Every issue carries **exactly one** of them. A second answer to one question is
a disagreement, and nothing resolves it.

`epic-child` is a supplemental marker. It makes a confirmed direct child of an
epic visible in a list. It is not an issue kind, does not decide readiness, and
may sit beside one of the six kinds.

**The routes are per harness, and they live beside this file.** Reading a
label and writing one are named in words here and resolved to a route there:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi,
[`references/codex.md`](references/codex.md) for Codex. Read the one for the
harness in use before writing a label.

<!-- issue-kind-labels-table -->

| Label | Description | Ready for an agent |
| ----- | ----------- | ------------------ |
| `epic` | Coordinates a sequence of other issues | Not `undertake`'s — `embark` takes one |
| `task` | Discrete work, specified and ready for an agent | Yes |
| `bug` | Bug report | Yes |
| `proposal` | Proposed feature | No — decompose it first |
| `research` | A question to settle | Yes |
| `human` | Work only a person can do | No — the work is a person's |

<!-- supplemental-labels-table -->

| Label | Description | Meaning |
| ----- | ----------- | ------- |
| `epic-child` | Direct sub-issue of an epic | Visual marker only; no readiness effect |

The descriptions are the ones GitHub shows, verbatim. They live twice — here
and in `infra/github/labels.tf` — and `scripts/check-labels.py` fails
`make check` when either table disagrees.


Picking one
===========

Ask the question in this order. The first answer that holds is the label.

1. **Does the issue describe work, or coordinate it?** An issue whose body is
   a list of other issues is an `epic`. It carries no code of its own, and the
   epic closes when its children do. `epic` is the skill that decides there is
   one and writes the children; this label is what the finished epic then
   carries.
2. **Can an agent do the work at all?** Where it cannot — credentials no
   agent holds, a decision only the user can make, an action outside the
   repository — it is `human`. The question comes before `bug`, `research` and
   `task`, because each of those three promises an agent may start and that
   promise is false whichever of the three the body would otherwise fit. It
   does not come before `proposal`, which is the last step's other answer: a
   wish whose shape is still open cannot be judged a person's to do, and
   deciding the shape is what settles which it is.
3. **Is it a bug report?** Then `bug`. Nothing here defines the word.
4. **Does it close on an answer rather than on a change?** A question to
   settle, an option to compare, a spike to run — `research`. What the answer
   produces is not fixed: a note under `docs/`, a set of task issues and an
   epic over them, or a decision not to do the thing at all. **A no is a
   finished `research` issue, not an abandoned one** — the question was
   settled, which is what the label promised.

   Where the answer is issues, writing them is `epic`'s, and they are the
   deliverable rather than a separate follow-up. Where it is code, that is a
   separate issue: the research closes, and a `task` opens.
5. **Is the intent settled?** Where what "done" means is written down and
   needs no further decision, it is a `task`. Where it is not — a capability
   somebody wants, with the shape of it still open — it is a `proposal`.

`proposal` and `task` are the same wish at two stages, and the line between
them is the constitution's rule against guessing at intent. A `proposal`
becomes one or more `task` issues when somebody decides what the work is; it
is not relabelled in place unless the whole of it fits one task.


What the label decides
======================

**Readiness, and nothing else.** `undertake` reads it at `Read the issue and
its edges`, and one label out of the six is a stop in three cases:

- An `epic` is a stop **for `undertake`**, which needs code to put on a
  branch and an epic has none. It is not a stop for every reader of the
  label: `embark` takes an epic directly and dispatches one ship per child. So
  the answer is `embark`, or the name of the child to work instead — not a
  refusal.
- A `proposal` is a stop. It is the vague-request case `Open the issue`
  already refuses to write an issue for, arriving with an issue already
  written. Deciding its shape is the user's and decomposing it is `epic`'s,
  so it goes to the user.
- A `human` is a stop, and the only one that is a stop for every reader of
  the label rather than for one skill. There is no agent route to the work,
  so `undertake` does not cut a branch for it and `embark` does not dispatch
  a ship for it: it waits for the person, and saying what the person has to
  do is the whole of the answer.

Two labels out of the six is a fourth stop, and it is below with its remedy.
`task` and `bug` run through, and both end in a pull request. **`research`
runs through and need not**: where the answer is a note it lands as a pull
request like any other, and where the answer is a set of issues or a no,
there is nothing to put on a branch. The issue closes on the answer either
way, and `undertake` is not the route for the two that carry no code.

The invariant at the top of this file breaks two ways, and they are answered
differently.

**No label at all is not a stop.** The issue is unlabelled rather than
blocked, and the answer is to label it: `Picking one` returns the label and
the issue client applies it, in passing, before the work goes on. `undertake`
labels every issue it opens and so does `epic`, so an unlabelled issue is one
a person opened. Naming the label without writing it leaves the next session to name
it again.

**Two of the six on one issue is a stop.** They are two answers to a single
question, and nothing here ranks them — a `proposal` that is also a `task`
says the shape is both open and settled, and picking either reading is
guessing at intent. Say which two are on it, say which one `Picking one`
returns, and wait. Adding rather than replacing is how it happens by
accident, so the reference file for a harness whose label write *adds* says
that a swap is one call carrying both the add and the remove. On a harness
whose write *replaces*, the swap is free and the read-first rule is what
bites instead: see `Where the standard is declared`.

Maintaining the epic-child marker
=================================

`issue-deps` owns parent edges. After it creates, changes, removes, or reads a
parent edge, it invokes this policy. Read the child's direct parent and read
that parent's labels. Add `epic-child` only when the confirmed parent carries
the `epic` kind. Remove it when the confirmed parent is absent or is not an
epic. Closing the child does not change a confirmed qualifying edge, so it
keeps the marker.

A failed or unavailable graph read is not evidence that a parent is absent.
Preserve the marker and report the limitation. Never create, change, or remove
an edge to justify a marker. Preserve the issue kind, stock labels, bot labels,
and unrelated labels on every marker write.


What a label is not
===================

- **Not a priority.** Nothing here reads one, and a priority nobody reads
  rots into a claim about what mattered last quarter.
- **Not a status.** An issue is open or closed, and what is happening to it
  in between is on the issue: `undertake` comments its claim at `Claim the
  issue`, and the pull request references it. A `in progress` label is a
  third copy of that, updated by hand, wrong first. **`human` is not the
  exception.** It says what the work is, so an issue does not become `human`
  because an agent got stuck on it this afternoon; that belongs in a comment,
  and the issue keeps the label its work earns.
- **Not a size.** An estimate is not a kind, and it does not change whether
  an agent may start.
- **Not a relationship authority.** Blocked-by, parent and sub-issue are edges
  in a graph GitHub keeps, and `issue-deps` owns reading and writing them.
  `epic-child` is the sole derived visual cue: it repeats a confirmed direct
  parent edge for lists, never replaces it, and cannot prove a relationship.

A repository wanting another relationship view wants a field or project board,
not another issue kind.


Labels outside the standard
===========================

A repository carries labels this standard does not define, and they are left
alone:

- **GitHub's stock set** — `enhancement`, `documentation`, `question`,
  `good first issue`, `help wanted`, `duplicate`, `invalid`, `wontfix`.
  Created with every repository, and none of them is read here. An issue
  carrying one still needs a label from the table above.
- **Labels a bot owns.** Dependabot applies `dependencies` and
  `github_actions`; release-please applies `autorelease: pending` and
  `autorelease: tagged`. These are machine state, they arrive on pull
  requests, and editing them breaks the tool that wrote them.

The standard governs what is *applied to an issue by a skill in this plugin*.
It does not claim the namespace, and it deletes nothing.

What the body carries
=====================

The label decides readiness; it does not decide what the body says. The body
requirements a labelled issue must satisfy are `issue-body`'s — which label's
contract applies, the readiness test an issue must pass before it is
presented as ready, and the `Model:` line a `task` body ends with. Read that
skill whenever a body is being written or revised, alongside the label picked
here.


Where the standard is declared
==============================

`infra/github/labels.tf` declares six issue kinds and the supplemental
`epic-child` `github_issue_label` resource. The names, colours and descriptions
come from a file under review rather than from whoever clicked last. OpenTofu
owns only what it declares, so stock labels survive an apply untouched.

Three consequences worth knowing:

- **A label that already exists must be imported before the first apply.**
  Creating one GitHub already has fails the apply rather than adopting it.
  `infra/github/import.sh` carries the import for `bug`, which every
  repository ships with. If somebody created `epic-child` before the managed
  apply, import it too.
- **Applying is a person's job.** `make check-infra` validates the stack
  without credentials, and CI runs it; the apply needs a token with admin
  rights and is not something a session does on its own.
- **A label applied to an issue before that apply creates itself.** GitHub
  makes a missing label the moment one is set on an issue, with a colour
  nobody chose — and the label then exists, so the first apply fails on it
  exactly as it would on `bug`. Import it rather than reading the failure as a
  broken stack.

Applying the standard to a repository that does not run this Tofu stack means
copying `labels.tf`, or creating the six kinds and `epic-child` by hand with
the descriptions in the tables above. The descriptions are what a person
hovering a label reads.
