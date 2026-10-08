# Model classes

Task issues name the minimum capability needed to implement their settled
handoff. The narrow frontier exception lets a `research` issue name a bounded
research or planning assignment. Classes remain provider-neutral: they do not
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
apply the task template to other issue kinds.

## Selection

At dispatch, filter candidates for the required class, tools, context,
modalities, and current availability. Prefer the lowest expected reliable cost,
including known rework and quota costs. Unknown or incomparable prices use the
operator's configured eligible preference; do not call missing or zero catalog
cost free. A stronger eligible model may run lower-class work. If no eligible
route exists, stop only that task and report the configuration gap.

An effective route that runs frontier requires explicit approval for that
assignment, even when a lower-class role, configured retry fallback, prewalk
fallback, or visible parent-model inheritance selects it. Resolve the effective
execution route, not only the requested role name. A harness-resolved
astra/fable route is frontier for this authorization check.

A frontier session assigned ordinary implementation hands it to an eligible
non-frontier route. It may perform only the bounded routing and handoff; it
does not retain or supervise the implementation on frontier. An approved
frontier research pass returns only its bounded deliverable; any implementation
work is handed to an eligible ordinary class unless the user separately
authorizes frontier implementation. If no eligible route or authorized
model-switch/delegation path exists, stop and report the configuration gap.
Frontier implementation requires explicit user authorization of that exception
and its bounded scope; research approval does not cover it. Non-frontier
standalone undertaking keeps its existing behavior.

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


