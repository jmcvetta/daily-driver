# Model classes

Task issues, and any `research` or `bug` issue proposed as an epic story, name
the minimum capability needed to deliver their settled handoff. The narrow
frontier exception lets a `research` issue name a bounded research or planning
assignment. Classes remain provider-neutral: they do not
name a provider, price tier, context window, or reasoning-effort setting.

## Classes

| Class | Suitable work | Boundary |
| --- | --- | --- |
| `mechanical` | A bounded transformation with an explicit rule, identified scope, existing example, and direct check. | No substantive implementation choice or diagnosis remains. |
| `implementation` | Settled design using repository patterns, routine local choices, ordinary multi-file coordination, meaningful tests, and local failure diagnosis. | The normal class for a specified feature or bug fix. |
| `reasoning` | A settled design with sustained reasoning about interacting invariants or difficult failure modes. | State the irreducible reason, such as concurrency correctness, security boundaries, or data integrity. File count, a security filename, and missing specification are not reasons. |
| `frontier` | Exceptional, bounded research or planning where the cheaper classes cannot reliably settle the named question. | Requires explicit user approval for the assignment and work envelope; never a default implementation route. |

Frontier does not mean difficult, underspecified, unavailable, or retrying.
Those conditions do not authorize its use. A frontier assignment states why the
three ordinary classes are insufficient.

Improve the task specification before raising its class. A stronger model does
not make an underspecified task ready.

## Authorization

Before publishing or revising an issue into a frontier assignment ready for
execution, stop and ask the user in chat for explicit confirmation. Explain why
`mechanical`, `implementation`, and `reasoning` cannot reliably deliver it.
Silence, broad plan approval, or the author's own judgement is not approval.
Approval of a plan counts only when it explicitly includes the frontier
assignment and its work envelope.

The request names the question or decision, known input scope, expected
deliverable, and proposed frontier sessions or passes. Separate known facts,
estimates, and unknowns. Do not perform the frontier work to estimate it.
Token, time, dollar, and subscription-quota estimates are optional; state them
only with evidence and assumptions. Otherwise say they are unknown.

Record the approval and approved work envelope in the issue handoff. Link its
source when one exists; do not fabricate a link for chat approval. Approval
covers only that assignment. Ask again before material scope expansion.

`research` may use frontier for a bounded research or planning assignment. In
that case the issue keeps its `research` label and single `## Model class`
token and rationale, followed by the approval record and work envelope. Do not
apply the task template to other issue kinds. A `research` or `bug` epic story
uses the same section and the ordinary classes' meanings; the class states the
capability needed to deliver that kind's settled handoff.

## Selection

For classed undertaking, select the exact required class within the invoking
family and provider before worktree or claim. Preserve backend and authentication
where supported; never deliberately substitute another provider. Assess tools,
context, modalities, availability, and visible fallbacks. A configured mapping
does not itself prove capability. Do not change shared roles or infer an
eligible route from price.

If the known family is absent from the class table, prominently warn with the
family, requested class, and retained provider/model. Continue immediately on
the invoking model, provider, and effort without confirmation. Class suitability
is unverified, even if execution identity is observed. Frontier authorization
and actual route constraints still apply. Do not use this exception for unknown
identity or for a mapped family with a missing or cleared class, unavailable
target, or incompatible assignment: report those configuration gaps.

An effective route that runs frontier requires explicit approval for that
assignment, even when a lower-class role, configured retry fallback, prewalk
fallback, or visible parent-model inheritance selects it. Resolve the effective
execution route, not only the requested role name. A harness-resolved
astra/fable route is frontier for this authorization check.

For a mapped family, prefer a verified in-session switch; use a full handoff
only where the surface can constrain and verify the same route. The receiving
session owns the undertaking and the sender stops. For an absent family, keep
the invoking session if a child cannot retain the route. An approved frontier
research pass returns
only its bounded deliverable; implementation requires a separately authorized
frontier exception or an eligible ordinary class. Frontier implementation
requires explicit user authorization and its bounded scope; research approval
does not cover it. Ordinary workers cannot fall back to frontier.

For an operator's manual escalation during a failing task, apply the
constitution's *Manual frontier escalation*: repair the plan and return the
existing work to an eligible ordinary worker. Manual escalation is authorized;
it is not a frontier implementation exception or an agent-initiated assignment.
Keep this consultation separate from the task's required class, assigned worker,
approval evidence, and execution verification. Operator model selection must
not be vetoed for missing assignment approval. It does not authorize unrelated
delegation or later automatic fallback.

A row in the harness reference's `Measured routes` table outranks this file's
hand-written `Classes` table. A missing row, or one marked `unmeasured` or
`unreported`, means the model is unmeasured. A stale row, judged from its
`Recorded` date, is read the same way. An unmeasured model is unknown, and
unknown falls to the operator's configured preference above.

Record the requested class separately from the selected route and actual model.
Use `unreported` when the harness does not report actual execution identity;
report visible runtime fallback mismatches and reassess before continuing.

This file stays provider-neutral by rule, so the generated measured-routes
table that cites real routes by name lives in the harness-specific reference
that resolves them -- currently [`omp.md`](omp.md)'s "Measured routes"
section.


