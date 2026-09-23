---
name: issue-body
description: >-
  This skill should be used whenever the body of a GitHub issue is being
  written or revised. It supplies the grounded handoff, readiness test, and
  provider-neutral model class for `task`; every other label's edit keeps its
  own body rules. It is invoked from `issue` and direct body edits. Not for
  labels, issue relationships, or pull request bodies.
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

**What is defined here is defined for `task` alone.** Every other label's
body properties are undefined by this skill: perform the requested edit under
the rules that already govern it and impose nothing — no task sections, no
model metadata, no generic template. The standard does not claim the
namespace, in the way `issue-labels` says of labels themselves.

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

**A task body opens in a fixed shape.** Its parts appear in this order:

1. **A one-line summary.** The first line states the observable outcome.
2. **A haiku.** Immediately after the summary, separated by a blank line:
   three 5-7-5 lines, italicised line by line, as
   [`HAIKU.md`](../../HAIKU.md) shows.
3. **`## Summary`.** A short human-facing paragraph or two describing the
   change and reason, without duplicating `Detail`.
4. **`## Model class`.** Immediately after `Summary`, before `Detail`. Its
   first paragraph is exactly one backtick-wrapped lowercase class token;
   one short rationale paragraph follows.
5. **`## Detail`.** The grounded map, settled design, acceptance, and
   verification. Its internal headings are the author's choice.

The class is implementation metadata, not authoring, review, judging, effort,
or concrete-model provenance. A task body has no trailing `Model:` or
`Effort:` line. This shape is `task`'s alone; an `epic` body is untouched.


**Relationships are edges, not prose.** What the task waits on is
`issue-deps`' to record, and a body states only what an edge cannot — that
rule is `issue-deps`'s, cited here rather than restated.


The readiness test
==================

Before an issue is presented as ready: **can an implementer assessed for the
chosen class implement it from the issue and referenced repository context,
without making an unstated product or architecture decision?**

A repository-answerable question is answered now, by the author. An unresolved
user decision means the task is not ready at any class. Unknown class tokens,
multiple class sections, and a missing rationale are invalid metadata, not a
default to `implementation`.


Updating a body
===============

An update preserves valid content. The user's content and requirements that
still hold stay; the affected specification changes; and readiness runs again.
Unrelated text is not reflowed and existing issues are not swept.

A deliberately revised task emits the new section and removes its trailing
task `Model:` field. When selecting an old task for work, assess its body
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
uses the issue body as concrete-model provenance. `undertake` checks the
current implementation session against the selected class before it claims or
changes repository files. Claim comments, readiness reports, and execution
records retain the concrete model the harness actually reports.
