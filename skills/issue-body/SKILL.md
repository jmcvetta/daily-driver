---
name: issue-body
description: >-
  Use whenever a GitHub issue body is written or revised. Selects the contract
  by effective issue kind, with that kind's readiness and completion test, the
  grounded `task` handoff, the class section every assignable epic story
  carries, and the frontier research exception. Not for labels, issue
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

Each of the eight managed kinds has a contract. `task`'s grounded handoff and
fixed opening are defined below. The `research`, `bug`, `proposal`,
`specification`, and `human` contracts are in
[`references/kind-contracts.md`](references/kind-contracts.md).
`epic` owns the parent contracts for both `epic` and `discovery`; invoke
[`epic/SKILL.md`](../epic/SKILL.md) rather than copying them here.
`issue-labels` owns kind selection. `story` and
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

**Class metadata is separate from the task template.** A `task` carries its
`## Model class` section in the fixed task shape. A `research` or `bug` issue
carries one only when it is an assignable epic story (see `Assignable stories`
below) or a frontier research assignment. It then carries just that section and
its rationale, and does not inherit the task template, haiku, implementation
map or fixed body shape. Every kind uses its own contract and gains no task
sections or generic template. Standalone bug filing and ordinary standalone
research stay unchanged and need no class.

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
3. **Grounded implementation map.** Scale repository investigation and
   pointers to the task's complexity and what the assigned worker needs.
   Cite relevant files, symbols, tests or gates when useful; never invent a
   path, API, command or detail.
4. **Settled design.** Resolve substantive contracts, invariants, edge cases,
   and compatibility or migration requirements. Routine local choices remain
   with the implementer.
5. **Acceptance and verification.** State observable pass/fail conditions,
   existing coverage, plausible regressions, and relevant project gates.
   Where integration uncertainty could invalidate the implementation route,
   name the bounded proof and the evidence that counts. For deployment work,
   record authoritative state and configuration, sensitive returned-state
   protection, recovery and resume requirements, and the approved resource
   lifecycle where they apply. Do not add mandatory headings or impose these
   details on unrelated work.
6. **Model class.** Choose the lowest class in
   [`references/model-classes.md`](references/model-classes.md) that can
   reliably implement the settled work. Improve the specification before
   raising the class; do not weaken scope or checks to choose a cheaper route.
   For research, frontier is the only class exception and does not add the task
   template.

**Write for the assigned worker, not for the author.** The planning agent is
ordinarily more capable than the worker its class selection routes to, and
nothing the author knows reaches that worker except through the body. A fact
the author read out of the repository, an inference drawn while planning, a
decision settled on the way to the issue: each goes in the body, or the
worker must reproduce it with less capability. Judge what counts as a routine
local choice against the assigned class, never against the author — a choice
that took the author reasoning is not routine for a cheaper worker. Settling
a decision in the issue spends nothing the author has not already spent;
leaving it open spends capability the worker may not have.

An issue body is a requirement source, not original user approval. Later issue
edits do not silently cancel agreed requirements for active work.

**Specification-backed task variant.** Reference one specific, stable parent
publication record and name the allocated requirement IDs and explicit
exclusions. The record owns the approved canonical path and exact merged
`master` commit; the task owns allocation, implementation map, verification
and class. Resolve that record and read the document at that commit; verify
the IDs exist, allocation and exclusions are unambiguous, and decomposition
was separately agreed. Missing, changed, ambiguous or inaccessible records
route to `epic`, never to the latest revision. Existing task contracts that
pin their own path and SHA remain valid and keep that binding; do not reinterpret
them as a newer publication. The document owns behavior and acceptance.

**A task body opens in a fixed shape.** Its parts appear in this order:

1. **A one-line summary.** The first line states the observable outcome.
2. **A haiku.** Immediately after the summary, separated by a blank line:
   three 5-7-5 lines, italicised line by line, as
   [`HAIKU.md`](../../HAIKU.md) shows.
3. **`## Human brief`.** A short paragraph or two describing the change and
   reason, without duplicating `Detail`. It is human-facing, so the
   constitution's audience rule governs it.
4. **`## Model class`.** Immediately after `Human brief`, before `Detail`. Its
   first paragraph is exactly one backtick-wrapped lowercase class token;
   one short rationale paragraph follows.
5. **`## Detail`.** The grounded map, settled design, acceptance, and
   verification. It is agent-facing: it keeps every fact the implementer
   needs and is not shortened to a reading budget. Its internal headings are
   the author's choice.

Where the work has nontrivial components, flow, state, or data movement,
the `Human brief` should include one Mermaid
diagram that reveals that structure. The diagram is optional, not a quota:
omit it when prose is clearer or the structure is trivial. A diagram replaces
prose that would otherwise explain the same structure — never acceptance
criteria, never an exact contract, and never the dependency graph, which
stays authoritative for execution ordering. Where a diagram and the text
disagree, the text wins and the diagram is corrected in the same turn. No
decorative or duplicate diagrams, no progress checklists, and no second
hand-maintained dependency record.

The class is implementation metadata, not authoring, review, judging, effort,
or concrete-model provenance. A task body has no trailing `Model:` or
`Effort:` line — that is class metadata's own shape, immediately below
`## Human brief`, and is a different thing from `provenance`'s block, which sits
below a `---` rule at the very end of the body and this rule does not touch.
This shape is `task`'s alone; an `epic` body is untouched.

Every complete issue-body draft follows the active harness route for
provenance. For Omp GitHub writes, keep the authored body free of a new block;
the wrapper attaches and deduplicates attribution. Other routes include the
block they will publish. Withholding a live write does not remove the
provenance requirement. Follow `provenance`'s placement, field, and
distinct-attribution rules on an edited issue.


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

- For `task`, ask whether an implementer at the issue's assigned class — not
  the author — can implement from the issue and referenced repository context
  without making an unstated product or architecture decision, and without
  rediscovering a fact or decision the author already reached.
- For `research`, ask whether an agent can investigate without guessing its
  purpose, evaluation criteria, permitted actions, or expected output. The
  unknown answer is not itself a defect.
- For `bug`, ask whether the incorrect behavior and expected contract are
  clear enough to begin bounded diagnosis. A reproduction is not mandatory.
- For `proposal`, readiness is for discussion only, never unattended
  implementation.
- For `specification`, readiness is for interactive collaboration, not
  unattended execution; unresolved decisions are expected on the issue.
- For `human`, readiness is for the responsible person to act without
  reconstructing the request. It is never agent-execution readiness.
- For `epic`, use both decomposition gates and the current graph, respecting
  explicit scheduling constraints not represented by edges.

Before presenting a task as ready or dispatching it, assess the handoff from
the assigned worker's class using the question above. Resolve repository-
answerable gaps and preserve actual decisions and constraints. Name relevant
files, symbols, tests and gates where needed for the worker; do not manufacture
detail for a simple task. Meaningful acceptance and verification remain
required. Routine local choices stay with the implementer.

For an executable evaluation command, resolve the subject and semantic judge
independently from the actual target, experiment, task defaults and explicit
overrides. A subject selector alone does not establish a non-default judge:
when `JUDGE` is unset, the task-pinned `agent_judge` remains in effect. Check
the selected judge's execution session and authorization boundary as well as
route compatibility. When the default route is not authorized, do not present
an unqualified command as executable. The issue body must either use a
supported validated alternative `JUDGE=<id>` in the execution, recording and
rerun paths, or include this exact sentence: “Not ready for unattended
execution; the operator must select an authorized judge before any run.”
Omit the unqualified command or mark it explicitly as non-executable until
selection. A warning outside the body does not make an unsafe command ready.
Do not infer a judge from the subject, invent a selector, alter grading
criteria, disable semantic grading, or treat the handoff itself as approval.
Preserve a caller-supplied valid judge, subject selection, bounds,
rerun restrictions, provenance, approval conditions and required record
fields, including the run identifier, requested and observed identities, and
case outcomes when assigned; carry these through recording and reruns. Keep
explicit completeness checks as acceptance criteria: listing required record
fields does not substitute for checking that each required outcome is present.
An authorized judge remains valid through its supported execution session. This
does not change the default judge or add an approval checkpoint.

When a genuine gap remains, state it precisely and do not present or dispatch
the issue as ready. A truthful parent edge may still be recorded under
`issue-deps`. Do not invent intent, weaken checks or raise the class to hide
the gap. A readiness certificate, checklist or narrated review is not required.

The detailed contracts for research, bug, proposal, specification, and human are in
[`references/kind-contracts.md`](references/kind-contracts.md). The epic
contract remains in [`epic/SKILL.md`](../epic/SKILL.md#the-epic-body).

A repository-answerable question is answered now by the author. An unresolved
user decision makes the issue unready at every class. Missing, duplicate or
invalid class metadata is not a product-readiness defect: assess the grounded
handoff and record the lowest reasonable class and rationale before or during
dispatch. Preserve an explicit recognized class even when its rationale is
missing, and record a grounded rationale without changing its capability
requirement; never default to `routine` without evidence. A `frontier`
assignment needs its rationale, not a separate approval record. Frontier
research remains `research` and carries no task template.

Preserve supplied execution bounds and applicable authority in a handoff.
Do not add an approval checkpoint for a requested operation merely because
it is disabled, unfamiliar, or covered by generic third-party permission
language. Do not invent a separate paid-run approval prerequisite for work
the assignment itself authorizes under `undertake`'s direct-request rule.
Name the applicable authority for a real checkpoint. Preserve genuine
exclusions, required bounds, and fresh-confirmation conditions.
An agent-written handoff is not user approval and cannot waive a restriction.

Assignable stories
==================

Before dispatch, a story must be assignable. Membership does not itself make a
story assignable. **Assignable is not the `task` kind.** It means:

1. An agent-eligible kind — `task`, `research` or `bug`. `proposal`,
   `specification`, `human` and `epic` are never assignable stories.
2. Ready under its own kind's readiness test above, with the kind's contract
   and completion test unchanged. A research story's unknown answer is not a
   defect. A bug story states the incorrect behavior, the expected contract,
   the bounded diagnosis and correction scope, and the completion evidence,
   without inventing an undiagnosed cause or a predetermined fix.
3. Its capability need is assessed from the grounded handoff. Record one valid
   `## Model class` section with a lowercase class token and short rationale
   before or during dispatch, including for research and bug stories. Place
   their section after the kind's opening content and before `provenance`'s
   trailing block. Preserve a supplied valid class.

Missing or malformed metadata does not itself make a substantively ready story
unready. Repair it from the handoff without blindly choosing `routine`. If the
capability requirement cannot be determined, report that uncertainty and use
an available route rather than inventing a class; record the assessment when
grounded. A `story` marker, parent edge or kind label alone proves no readiness.

Resolve repository-answerable gaps before presenting a story as ready, and
preserve valid existing content under the update rule below. Do not invent
scope, silently relabel a kind, or manufacture a replacement issue; report
unresolved intent or an unavailable prerequisite precisely. An open
legitimate blocker does not make a story unassignable.
A GitHub assignee and an available concrete model are not required.

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
Unrelated text is not reflowed and existing issues are not swept. Preserve the
entire original provenance block, including all fields and values, exactly
below the body's closing rule. A `Model:` inside that block is provenance, not
task metadata; never move its fields into the task sections.

When asked to show a revised body, include the complete body and its unchanged
provenance block; attribution is part of the delivered revision, not optional
reporting.

A deliberately revised task emits the new section and removes its trailing
task `Model:` field — the legacy class-metadata field below `## Human brief`, never
a `provenance` block below the closing `---` rule, which follows `provenance`'s
distinct-attribution rule. When selecting an old issue for work, assess its body
against the class rubric and migrate only that issue before or during dispatch.
Use the grounded handoff to assess legacy `standard` or `advanced` metadata;
preserve its rationale and capability requirement rather than inferring a class
from the old identifier. A valid new section is authoritative when both forms
exist.


The model class section
=======================

The section is immediately below `## Human brief` and before `## Detail`:

```markdown
## Model class

`routine`

The API contract and edge cases are fixed; implementation follows the existing
adapter pattern.
```

`undertake` assesses class and, where grounded, records missing or legacy
metadata before or during dispatch for a classed `task`, `research` or `bug`.
It attempts the initial class selection once through the active harness's
configuration authority before worktree creation or claim. Omp uses its
effective class role, including model/provider and effort; Claude Code retains
its supported class-appropriate route. Failure is informational: name the
attempted target, failure and actual route, then continue ordinary work without
confirmation or repair. Later operator choices and resume never reselect.
Claim comments and execution records retain the observed model.
