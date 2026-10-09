---
name: issue-body
description: >-
  This skill should be used whenever the body of a GitHub issue is being
  written or revised. It supplies the grounded handoff and readiness test for
  `task`, the provider-neutral class contract, and the narrow approval-gated
  frontier research exception. Other labels keep their existing body rules.
  It is invoked from `issue` and direct body edits. Not for labels, issue
  relationships, or pull request bodies.
---

# Issue body

What a GitHub issue's body must carry, decided by the label the issue carries.
A body is written through `issue`, or by a session editing one directly —
both routes land here, which is the point: **there is no edit of an issue
body that bypasses this contract.**

The label decides which rules apply, and `issue-labels` owns the label. Work
from the **effective** label — the one the issue carries after the requested
change — not the one it carried before: relabelling `proposal` to `task`
makes it a task body from that edit onward.

**Task requirements are defined here for `task` alone, with one narrow
exception.** A `research` issue using the `frontier` class carries only its
single class section, rationale, explicit approval record, and approved work
envelope. It does not inherit the task template. Every other issue kind keeps
its existing body rules and gains no task sections or generic template.

**The routes are per harness, and they live beside this file.** The calls
that open an issue or replace its body are in
[`references/claude.md`](references/claude.md),
[`references/omp.md`](references/omp.md), and
[`references/codex.md`](references/codex.md). The class definitions and
changeable routing guidance are in
[`references/model-classes.md`](references/model-classes.md). Read the
applicable route and the shared guidance before the first call.


The task body
=============

Six information requirements. **They are requirements on information, not a
quota of headings or paragraphs** — a small task stays small, and
inapplicable detail is omitted rather than manufactured into boilerplate.

1. **Outcome and reason.** The observable change, current behaviour, and why
   the change is needed.
2. **Scope.** What changes, what remains unchanged, and explicit non-goals.
   One task is one reviewable pull request; use `epic` only where its gates
   hold.
3. **Grounded implementation map.** Inspect repository guidance, affected
   files, symbols, callers, tests, and gates. Reference that context; never
   invent a path, API, or command.
4. **Settled design.** Resolve substantive contracts, invariants, edge cases,
   and compatibility or migration requirements. Routine local choices remain
   with the implementer.
5. **Acceptance and verification.** State observable pass/fail conditions,
   existing coverage, plausible regressions, and relevant project gates.
6. **Model class.** Choose the lowest class in
   [`references/model-classes.md`](references/model-classes.md) that can
   reliably implement the settled work. Improve the specification before
   raising the class; do not weaken scope or checks to choose a cheaper route.
   A frontier task also needs the explicit approval and work envelope below.
   For research, frontier is the only class exception and does not add the task
   template.

**A task body opens in a fixed shape.** Its parts appear in this order:

1. **A one-line summary.** The first line states the observable outcome.
2. **A haiku.** Immediately after the summary, separated by a blank line:
   three 5-7-5 lines, italicised line by line, as
   [`HAIKU.md`](../../HAIKU.md) shows.
3. **`## Summary`.** A short paragraph or two describing the change and
   reason, without duplicating `Detail`. It is human-facing, so the
   constitution's audience rule governs it.
4. **`## Model class`.** Immediately after `Summary`, before `Detail`. Its
   first paragraph is exactly one backtick-wrapped lowercase class token;
   one short rationale paragraph follows.
5. **`## Detail`.** The grounded map, settled design, acceptance, and
   verification. It is agent-facing: it keeps every fact the implementer
   needs and is not shortened to a reading budget. Its internal headings are
   the author's choice.

The class is implementation metadata, not authoring, review, judging, effort,
or concrete-model provenance. A task body has no trailing `Model:` or
`Effort:` line — that is class metadata's own shape, immediately below
`## Summary`, and is a different thing from `provenance`'s block, which sits
below a `---` rule at the very end of the body and this rule does not touch.
This shape is `task`'s alone; an `epic` body is untouched.
Frontier authorization
----------------------

**Do not publish or revise an issue into a ready frontier assignment before
approval.** When the author judges frontier necessary, stop and ask the user
in chat for explicit confirmation. State why the three ordinary classes cannot
reliably settle the work. Give the bounded work envelope: question or decision,
known input scope, expected deliverable, and proposed frontier sessions or
passes. Distinguish facts, estimates, and unknowns; do not perform frontier
research to estimate it. State token, duration, cost, or quota as unknown
unless comparable measurements and assumptions support an estimate.

Use chat prose under `judgement-call`; its ordinary choice gate does not waive
this required confirmation.

Silence, broad plan approval, and the author's judgement do not count. Plan
approval counts only when the plan named the frontier assignment and estimate.
If the user denies it, do not publish the frontier assignment; use a cheaper
class only if it can meet the same settled contract, otherwise stop and report
the decision needed.
If the proposed assignment includes frontier implementation, the confirmation
must explicitly authorize that implementation exception and its bounded scope.
Approval for frontier research or planning alone does not qualify.

After approval, record its exact scope and approval source in the issue
handoff. Link an external source when one exists; chat-only approval has no
fabricated link. For frontier implementation, record the explicit exception
separately from any research or planning approval. For a frontier `research`
issue, add only the `Model class` section, rationale, approval record, and work
envelope. A task issue retains its normal body sections and puts the
authorization record in `Detail`. Ask again before materially expanding the
approved assignment.

**The write that lands this body also carries `provenance`'s block**, per
that skill's placement and field rules — a different thing from either
metadata field above, and unaffected by the migration rule below.


**Relationships are edges, not prose.** What the task waits on is
`issue-deps`' to record, and a body states only what an edge cannot — that
rule is `issue-deps`'s, cited here rather than restated.


The readiness test
==================

Before an issue is presented as ready: **can the assigned route deliver the
settled work from the issue and referenced repository context, without making
an unstated product or architecture decision?**

A repository-answerable question is answered now, by the author. An unresolved
user decision means the issue is not ready at any class. Unknown class tokens,
multiple class sections, and a missing rationale are invalid metadata, not a
default to `implementation`. A frontier assignment is not ready unless its
approval record and work envelope match the assignment exactly; a frontier
research issue remains `research` and carries no task template.


Updating a body
===============

An update preserves valid content. The user's content and requirements that
still hold stay; the affected specification changes; and readiness runs again.
Unrelated text is not reflowed and existing issues are not swept.

A deliberately revised task emits the new section and removes its trailing
task `Model:` field — the legacy class-metadata field below `## Summary`, never
a `provenance` block below the closing `---` rule, which this migration
leaves alone. When selecting an old task for work, assess its body
against the class rubric and migrate only that issue before dispatch. Map the
former `standard` class to `implementation` and `advanced` to `reasoning`, based
on the grounded handoff; do not change its rationale or capability requirement,
and do not infer a class from the old identifier. A valid new section is
authoritative when both forms exist.


The model class section
=======================

The section is immediately below `## Summary` and before `## Detail`:

```markdown
## Model class

`implementation`

The API contract and edge cases are fixed; implementation follows the existing
adapter pattern.
```

`embark` resolves the required class to an eligible concrete route. It never
uses the issue body as concrete-model provenance. `undertake` validates the
section and repairs an old or invalid body before its claim. A non-frontier
standalone session does not gate on its own identity, but a frontier session
must hand ordinary implementation to an eligible non-frontier route or stop
with a configuration gap. Any frontier assignment must carry explicit user
approval and its exact envelope before execution. Claim comments, readiness
reports, and execution records retain the concrete model the harness reports.
