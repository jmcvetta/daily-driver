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
| `routine` | Ordinary settled implementation using established repository patterns. | The normal class for a specified feature or bug fix, even when several files change. |
| `intermediate` | Work beyond routine that does not require the sustained difficult analysis of complex work. | Name the interacting components or contracts and the behavior to preserve. |
| `complex` | Settled work involving difficult behavior, correctness, or failure modes. | State the irreducible reason, such as concurrency correctness, security boundaries, or data integrity. |
| `frontier` | Exceptional, bounded research or planning where the cheaper classes cannot reliably settle the named question. | Never a default implementation route. |

For example, adding a field through an established API, state, and UI path is
`routine`. A settled persisted-state transition affecting execution,
recovery, hooks, and resume is `intermediate`. Making task claiming exactly-once
under concurrent workers, retries, and stale ownership is `complex`.

Frontier does not mean difficult, underspecified, unavailable, or retrying.
Those conditions do not authorize its use. A frontier assignment states why the
four ordinary classes are insufficient.

Improve the task specification before raising its class. A stronger model does
not make an underspecified task ready.

A frontier assignment's `## Model class` section and rationale carry its
capability decision; no separate approval record is required.

For missing or legacy metadata, assess the grounded handoff and record the
lowest reasonable class and rationale before or during dispatch. Preserve an
explicit recognized class and its capability requirement even if its rationale
is missing. Formatting is not product readiness; do not invent a class or
default to `routine` when the need is unclear. Report uncertainty and continue
settled work on an available route.

## Selection

When the class is grounded, attempt initial selection once before worktree or
claim through the active harness's configuration authority. Omp's effective class role governs model,
provider and effort together, even across families/providers. Claude Code
retains automatic class-appropriate selection through its supported mechanism;
a full handoff is optional when that route supports it.

Missing, cleared, invalid or unavailable assignments, unsupported controls,
credentials, rejected setters and persistence failures are informational.
Briefly report the requested class, attempted target, failure and actual route,
then continue ordinary work without confirmation or repair. Never claim that
missing credentials work or that a partial switch retained the invoking route.
Explicit cancellation remains a stop.

After initial selection, operator model, provider, and effort changes remain
permitted and must not be blocked or reversed, including after rejection or
resume. Agent-initiated worker, provider, and fallback choices are not
restricted by the undertaking router. The initial selection records the class
and model chosen at the start; it is not a continuing permission check.

`research` may use frontier for a bounded research or planning assignment. In
that case the issue keeps its `research` label and single `## Model class`
token and rationale. Do not apply the task template to other issue kinds. A
`research` or `bug` epic story uses the same section and the ordinary classes'
meanings; the class states the capability needed to deliver that kind's
settled handoff.

Measured-route tables provide evidence, not admission rules. They do not
override the operator's effective Omp role assignment. An unfamiliar model name
or absent benchmark does not justify substituting another model.

Record the requested class separately from the initial selected route and actual
model. Use `unreported` when the harness does not report actual execution
identity, and record the observed model when it differs.

This file stays provider-neutral by rule, so the generated measured-routes
table that cites real routes by name lives in the harness-specific reference
that resolves them -- currently [`omp.md`](omp.md)'s "Measured routes"
section.


