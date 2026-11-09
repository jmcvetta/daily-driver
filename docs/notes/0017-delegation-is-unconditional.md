# Delegation is unconditional — the orchestrator never implements

**Status:** superseded in part, 2026-09-17, by
[`0019`](0019-the-undertaker-implements.md), which keeps the rule inside
`embark` and drops it from `undertake`: delegation buys parallelism across
task issues, and there is none to buy inside one undertaking.
Decided 2026-09-15.
**Resolves:** [#251](https://github.com/jmcvetta/daily-driver/issues/251).

**Observed.** On `jmcvetta/career` epic #283, "undertake 283" read the epic,
named the ready wave, picked #334 — and implemented it in the orchestrator
session itself: 21 files, the gates, the pull request, the review round, all
in one context. Any parallel wave the operator wanted would have been
serialised through that one context, and the orchestrator paid the full cost
of an implementation it was never meant to touch.

## Why it could happen

Three escape hatches, all around delegation:

1. `embark`'s fallback model rule said the two exceptions — security-sensitive
   work, and work whose complexity makes a weaker implementor unsafe — were
   "dispatched to a stronger implementor, **or taken by the orchestrator
   itself**".
2. `embark`'s non-goal "Does not fire on one issue" left a single-task
   undertaking with no delegation route at all, and `undertake`'s `Implement`
   step had no delegation instruction of its own — a directly-invoked task ran
   in whatever session was invoked.
3. Nothing anywhere said the orchestrator could not review nothing and still
   implement everything.

## Decided

**Delegation is unconditional on a surface that has a subagent or session
route.** The orchestrator keeps responsibility for claim, dispatch, watch and
gates, and never implements — whatever the wave's size, whatever the task's
size. A dispatched implementor implements in its own session and does not
re-dispatch.

- **The cheaper-default rule stands.** A task body that meets `issue-body`'s
  contract is often executable by a cheaper-than-orchestrator model; that is
  the payoff of planning well. The strength upgrade stays the bounded
  exception: security-sensitive work, and work a weaker implementor cannot be
  trusted with, is dispatched to a **stronger subagent or session** — never to
  the orchestrator's own hands.
- **"Too complex for a weaker implementor" is a planning-defect signal, not an
  escape hatch.** A task that genuinely needs the orchestrator's strength was
  underspecified: its body failed the readiness test — can another agent
  implement it without making an unstated decision? The fix is back into the
  task body through `epic` — tighter grounding, settled choices — reported,
  not absorbed.
- **The single-task case is covered.** `embark`-of-one does not fire, but its
  delegation rule holds: `undertake`'s `Implement` now dispatches an
  implementor subagent and keeps claim, pull request, watch and gates in the
  orchestrator. Where a surface has no subagent route, the sequence runs in
  the invoking session, which is then the implementor by necessity, not by
  choice.
- **The orchestrator never reviews its own implementor's work.** The
  strong-model review gate in `Open the sessions` composes unchanged — with a
  delegating orchestrator, the advisor and the reviewer are naturally at
  orchestrator strength.

## Where it landed

`skills/embark/SKILL.md` (`Open the sessions`, `Non-goals`),
`skills/undertake/SKILL.md` (`Implement`), `skills/embark/references/omp.md`
(the one route table that carried the escape), and the three
`skills/undertake/references/{claude,omp,codex}.md` route tables, which now
name the dispatch call each surface uses. No step was renamed;
`scripts/check-step-names.py` is untouched.
