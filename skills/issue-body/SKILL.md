---
name: issue-body
description: >-
  This skill should be used whenever the body of a GitHub issue is being
  written or revised — including when the user says "write the issue body",
  "update #123's body", or asks for an issue to be made ready for an agent,
  and including any call Claude makes on its own initiative that sets an issue
  `body`. It is invoked from `issue` and also fires on direct body edits, so
  no write bypasses it. Supplies what a `task` issue's body must carry — the
  grounded handoff, the readiness test, and the `Model:` line — and the update
  rule that preserves valid content. Any other label's edit runs under the
  rules that already govern it and acquires nothing here. Not for the label
  itself, which is `issue-labels`, for the relationship graph, which is
  `issue-deps`, or for a pull request body, which is `pr-body`.
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
that open an issue or replace its body, and the model identifiers a `Model:`
line may name, are in [`references/claude.md`](references/claude.md),
[`references/omp.md`](references/omp.md) and
[`references/codex.md`](references/codex.md). Read the one for the harness in
use before the first call.


The task body
=============

Six information requirements. **They are requirements on information, not a
quota of headings or paragraphs** — a small task stays small, and
inapplicable detail is omitted rather than manufactured into boilerplate.

1. **Outcome and reason.** The observable change, the current behaviour, and
   why the change is needed.
2. **Scope.** What must change, what must remain unchanged, and the explicit
   non-goals. One task is one reviewable pull request; `epic` is used only
   where its own gates hold.
3. **Grounded implementation map.** Written after inspecting the repository
   guidance and the relevant code, not from memory: the affected files,
   symbols or sections, the existing patterns to follow, and the relevant
   callers. Reference the context rather than copying source into the issue.
   **Never invent a path, an API, or a command** — a handoff that sends its
   implementer to a file that does not exist is worse than none.
4. **Settled design.** The substantive engineering choices are resolved at
   authoring time: the contracts that change, the invariants, the edge cases
   that matter, and the compatibility or migration requirements where they
   apply. Routine local choices stay with the implementer — prescribing every
   line is not grounding, it is dictation.
5. **Acceptance and verification.** The observable pass/fail conditions, the
   existing tests, fixtures and project gates that cover the change —
   identified through inspection, not assumed — and the plausible regressions
   coverage must catch. Tests are not required of prose or plumbing merely to
   fill a template.
6. **Execution model.** The lightest agent that can execute the task
   reliably, chosen by the model and harness conventions that already exist,
   written as the `Model:` line below. Heavier capability is justified in a
   sentence when it is necessary: cost comes down by removing uncertainty,
   never by weakening a quality gate or by assigning arbitrary work to the
   smallest model.

**Relationships are edges, not prose.** What the task waits on is
`issue-deps`' to record, and a body states only what an edge cannot — that
rule is `issue-deps`'s, cited here rather than restated.


The readiness test
==================

Before an issue is presented as ready: **can another agent implement it from
the issue and the repository context it references, without making an
unstated product or architecture decision?**

A repository-answerable question is answered now, by the author — that is
what the implementation map is for, not work delegated to whoever implements.
An unresolved decision that belongs to the user is asked about, and until it
is answered the issue is not ready. **Never fabricate certainty, and never
silently change scope or a label to pass the gate.**


Updating a body
===============

An update preserves what is valid. The user's content and the requirements
that still hold stay; the affected part of the specification changes; the
readiness test runs again. Unrelated text is not reflowed, and existing
issues are not swept. Where an implementation later contradicts what the
handoff assumed, the discrepancy is reported rather than the stale
instructions followed blindly.


The Model line
==============

A task body's last line, and nothing after it:

```
Model: <identifier>
```

The identifier is the lightest one that can execute the task reliably, in the
form the harness's session client accepts — the reference file for the
harness in use names them, and it is read rather than recalled. **Where no
valid identifier can be named, write no line at all**: a missing line is a
working default on every route, and a session opened on a model that does not
exist is not.

**Reasoning effort cannot be recorded.** The session clients take a model and
have no effort parameter, so an `Effort:` line beside the model would be read
by nothing. Do not write one.

`embark` parses this line to dispatch each task's session, and the format
above is what it parses. The line therefore lives here and nowhere else — a
second copy of the format is a second thing `embark` would have to follow.
