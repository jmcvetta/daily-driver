# Settled work uses routine workers

**Status:** decided, 2026-11-25.
**Resolves:** [#1120](https://github.com/jmcvetta/daily-driver/issues/1120).
**Supersedes:** [`0019`](0019-the-undertaker-implements.md), only where it says that undertaking implementation delegation buys parallelism or nothing and that the undertaking owner must write the body of the work. The duplicate-full-undertaking failure and the remaining ownership boundaries in `0019` still hold.

## Decision

**The undertaking owner keeps the outcome; a routine worker may execute a settled component slice.** After the owner has interpreted requirements, made design and decomposition decisions, and can state acceptance precisely, prefer one bounded `routine` handoff for a coherent implementation slice when it is likely to cost less overall than the owner's long mundane execution loop plus the coordination and review overhead. A small slice, judgment-dense work, or requirements that are not yet precise stay with the owner. `intermediate` remains available for a bounded slice that needs local judgment beyond routine execution; it is not the default for tests, documentation, checks, or mechanical corrections.

The owner remains responsible for requirements interpretation, design, decomposition, risky integration proof, scope and authorization control, integration, and final acceptance. The worker brief states:

- required behavior, acceptance criteria, and settled design decisions;
- owned files, explicit non-goals, scope limits, and applicable authorization conditions;
- meaningful test scenarios and named verification commands;
- one clear writer per file and the owner's integration responsibility; and
- the requested result: changes, observed verification, and unresolved exceptions.

The worker may implement the scoped code, tests and documentation, run the named focused checks, and correct ordinary local failures within the brief. It returns to the owner on a requirements contradiction, unsettled design choice, authorization boundary, or failure outside its scope. It never silently expands scope. Use one coherent implementation worker by default; parallelize only genuinely independent slices with disjoint file ownership. Do not create a worker for each command, tiny edit, test run, or review finding. A worker's implementation is not independent review of its behavior.

## Review corrections

During `review-cycle`'s `Fix, answer, resolve, push`, the owner first triages findings and keeps judgment-dependent dispositions, thread answers, and scope control. The owner may delegate mechanical corrections as one bounded `routine` batch when that removes a substantial mundane fix loop. The owner supplies the relevant findings, files, acceptance and named checks, integrates the result, and retains responsibility for the review threads. `Verify the fix delta` remains an independent pass after the pushed batch; the worker cannot verify its own changes.

## Omp boundary

A component worker uses the existing Omp subagent route with `agent: "routine"` and the owner's task-worktree path. It is not a second full `/undertake` handoff: it creates no separate claim, branch, pull request, or readiness gate. The owner continues the issue sequence and owns integration and acceptance.

## Consequences

`skills/undertake/SKILL.md` sets the cost-aware default, owner responsibilities, brief contents, and escalation boundary. `skills/review-cycle/SKILL.md` allows one post-triage mechanical fix batch while keeping dispositions and the independent fix-delta pass with the owner. The Omp route distinguishes component execution from a full undertaking handoff. Focused behavior cases cover settled implementation dispatch and a triaged mechanical fix batch.
