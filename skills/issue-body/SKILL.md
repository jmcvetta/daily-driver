---
name: issue-body
description: >-
  This skill should be used whenever the body of a GitHub issue is being
  written or revised. It selects the body contract by effective issue kind,
  including each kind's readiness and completion test. It supplies the grounded
  handoff for `task`, the provider-neutral class contract, and the narrow
  approval-gated frontier research exception. It is invoked from `issue` and
  direct body edits. Not for labels, issue relationships, or pull request bodies.
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

Each of the six managed kinds has a contract. `task`'s grounded handoff and
fixed opening are defined below. The `research`, `bug`, `proposal`, and
`human` contracts are in
[`references/kind-contracts.md`](references/kind-contracts.md).
`epic`'s existing body contract remains in
[`epic/SKILL.md`](../epic/SKILL.md#the-epic-body); invoke it rather than
copying its format here. `issue-labels` owns kind selection. `story` and
unrelated labels add no body contract.

These are information requirements, not a quota of headings. Keep small
issues small, omit inapplicable fields, and do not invent facts. Separate
supplied observations, inspected evidence, assumptions, and open questions.
Kind eligibility and body sufficiency are separate: an eligible kind's body
can still fail its readiness test. A valid proposal remains non-executable,
and a complete human handoff remains human work.

When a body changes, use the effective kind after a requested relabel.
Preserve valid requirements, evidence, and provenance history. Remove obsolete
task-format scaffolding when it no longer applies, retaining its substantive
information in the selected contract. Do not migrate unrelated issues or
reflow a body for an unrelated label or state change.

**Task class requirements are defined for `task`, with one narrow exception.**
A `research` issue assigned `frontier` carries only its single class section,
rationale, explicit approval record, and approved work envelope. It does not
inherit the task template. Every other kind uses its own contract and gains no
task sections or generic template.

**The routes are per harness, and they live beside this file.** The calls
that open an issue or replace its body are in
[`references/claude.md`](references/claude.md),
[`references/omp.md`](references/omp.md), and
[`references/codex.md`](references/codex.md). The selected non-task contracts
are in [`references/kind-contracts.md`](references/kind-contracts.md); the
epic format remains in
[`epic/SKILL.md`](../epic/SKILL.md#the-epic-body). The class definitions and
changeable routing guidance are in
[`references/model-classes.md`](references/model-classes.md). Read the
applicable route and shared contract before the first call.


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

Every complete issue-body draft intended for a write includes the block it
would publish. Withholding the live write does not remove the provenance
requirement. Follow `provenance`'s placement and field rules, and preserve
earlier provenance blocks on an edited issue.


**Relationships are edges, not prose.** What an issue waits on is
`issue-deps`' to record; the body states only what an edge cannot.


The readiness test
==================

Apply the selected kind's readiness test before unattended work starts.
Eligibility of a kind does not make an issue body sufficient. Resolve
repository-answerable gaps. Ask only for intent or another prerequisite that
cannot be answered from available evidence. Do not silently change a bug or
research issue to `human` because an agent is blocked.

Before an issue is presented as ready, ask: can the assigned route deliver the
settled work from the issue and referenced repository context without making
an unstated product or architecture decision?

- For `task`, ask whether an implementer assessed for its class can implement
  from the issue and referenced repository context without making an unstated
  product or architecture decision.
- For `research`, ask whether an agent can investigate without guessing its
  purpose, evaluation criteria, permitted actions, or expected output. The
  unknown answer is not itself a defect.
- For `bug`, ask whether the incorrect behavior and expected contract are
  clear enough to begin bounded diagnosis. A reproduction is not mandatory.
- For `proposal`, readiness is for discussion only, never unattended
  implementation.
- For `human`, readiness is for the responsible person to act without
  reconstructing the request. It is never agent-execution readiness.
- For `epic`, use both existing epic decomposition gates and confirm the graph
  agrees with its rendered waves.

The detailed contracts for research, bug, proposal, and human are in
[`references/kind-contracts.md`](references/kind-contracts.md). The epic
contract remains in [`epic/SKILL.md`](../epic/SKILL.md#the-epic-body).

A repository-answerable question is answered now by the author. An unresolved
user decision makes the issue unready at every class. Unknown class tokens,
multiple class sections, and a missing rationale are invalid metadata, not a
default to `implementation`. A `frontier` assignment is not ready unless its
approval record and work envelope match the assignment exactly. Frontier
research remains `research` and carries no task template.

Task completion
===============

A task completes when its specified observable change is delivered and its
required verification passes. A commit or pull request being opened is not
completion by itself. The acceptance criteria and verification in the task
body define the evidence.


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
