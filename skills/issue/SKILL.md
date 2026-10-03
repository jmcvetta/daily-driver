---
name: issue
description: >-
  This skill should be used whenever a GitHub issue is being opened or updated
  — including when the user says "/issue", "open an issue for this", "update
  #123", or asks for an issue's body, label or state to change, and before
  opening or updating an issue, or changing its body, label or state. Reads the
  issue's existing state before any edit. The body's content is `issue-body`'s,
  the label is `issue-labels`'s, the relationship graph is `issue-deps`'s; each
  is invoked rather than restated. Not for read-only discussion of an issue,
  for a comment alone, or for taking an issue to a pull request — that is
  `undertake`.
---

# Issue authoring
Open a GitHub issue, or change one that exists. This skill is the entry
point for every issue write a session makes directly — its own, and
`undertake`'s at `Open the issue`. `epic`'s writes at `Open the issues`
reach the same body contract through `issue-body`, not through this
sequence.

It is an orchestrator, in the same shape as `pr`: **it invokes, it does not
restate**. The body's content is `issue-body`'s, the label standard is
`issue-labels`'s, and the relationship graph is `issue-deps`'s. Where a move
below names a rule one of those owns, it names it as a pointer and cites the
owner — a rule that acquires a second home here is one whose copy goes stale.

**Writing an issue is not starting the work.** This skill opens and updates
issues and stops there. Taking an issue to a pull request is `undertake`'s,
entered deliberately, and never by this skill: an issue written
mid-implementation is a record made after the decisions it was meant to hold.

**The routes are per harness, and they live beside this file.** Every call the
moves below need is named in words here and resolved to a route there:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi,
[`references/codex.md`](references/codex.md) for Codex. Read the one for the
harness in use before the first call.

Automatic Daily Driver bug reports
==================================

When a Daily Driver skill, script, hook, extension, or supplied
harness-specific command is confirmed defective, file a brief report in
`jmcvetta/daily-driver` without asking permission. Confirmation must distinguish
the component from invalid input, caller misuse, missing credentials, a target
repository defect, and a third-party failure. A failed command alone does not
establish ownership. Read the relevant documented behavior and available
evidence; use a safe, bounded reproduction only when needed. Do not repeat an
already-established failure or require a complete root-cause investigation.

Use the title `[auto-filed] <short defect description>` and the existing `bug`
label. Keep the body short: name the affected component, expected and observed
behavior, and the minimal available reproduction or error evidence that
establishes Daily Driver ownership. Include relevant version and context when
available, redact secrets and private project data, and end with
`provenance`'s block. Do not add task sections, a model class, a task template,
a haiku, an implementation map, an acceptance plan, or a proposed fix.

If attribution remains uncertain, investigate only as needed to resolve it;
do not file an asserted bug based on suspicion. Target-repository defects
continue through their normal fix path. After filing, report the issue link
and return to the original work where safe. Filing does not authorize a
workaround, require the same session to fix Daily Driver, or override another
safety rule. If the defect blocks the work, report that blocker. If GitHub
filing fails, report the actual failure and do not claim that an issue exists.



What fires, and what does not
=============================

Fires: an issue being opened, and an issue being updated — its body, its
label, its state — whether the user asked in words or the session reached for
its own issue client. **The session's own writes fire it too.** An agent
labelling an unlabelled issue, or rewriting a body, is an issue update like
any other, and the same read-first rule applies to it.

Does not fire: reading an issue, discussing one, answering a question from it
— read-only work is no skill's business here. **A comment alone does not fire
it either.** A claim, a report, an answer is prose on an issue, not a change
to one. Comments happen inside other sequences — `undertake`'s `Claim the
issue` among them — and not through here.


The moves
=========

In order, and each only when the change needs it:

**Read what is there.** The issue's current state — body, labels, edges —
before any edit. An update that does not start from what the issue says now is
a rewrite of something nobody read, and `issue-body`'s update rule depends on
the read. On a new issue there is nothing to read; on an existing one it is
not optional.

**The label.** `issue-labels` picks it, and repairs an issue carrying none in
passing. On a requested relabel, the **effective** label — the one the issue
carries after the change — is what the rest of the sequence works from: a
`proposal` becoming a `task` is a task body from that edit onward, not the
next time somebody remembers.

**The body.** `issue-body` owns what a body must carry. It fires on this
skill's writes and on direct edits alike, so there is no route past it — which
is why nothing here restates it.

**The edges.** `issue-deps` owns blocked-by, parent and sub-issue. A body
never states in prose what an edge records; that rule is `issue-deps`'s, cited
here rather than restated.

**The close, when it is not planned.** An issue closed with `state_reason:
not_planned` gets one comment with the state change: a line saying why the
work will not be done, `provenance`'s block, and last a short elegy for it —
two to four lines, each italicised as [`HAIKU.md`](../../HAIKU.md) shows.
The reason comes first so a reader never reads past verse to learn it. A
close as `completed` or `duplicate` carries no elegy: the work was done, or
lives on elsewhere.


Non-goals
=========

- **Does not implement.** Writing an issue must never start the work it
  describes. `undertake` is the route from an issue to a pull request, and
  this skill does not enter it.
- **Does not decompose.** Work too big for one issue is `epic`'s, which writes
  task bodies under `issue-body`'s contract. This skill never calls `epic`
  back: there is no recursion among `issue`, `undertake` and `epic`.
- **Does not standardise titles.** Titles stay as the request left them. No
  title skill exists, and none is implied by this one.
