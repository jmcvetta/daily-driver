# The undertaker implements — delegation buys parallelism or nothing

**Status:** decided, 2026-09-17.
**Supersedes:** [`0017`](0017-delegation-is-unconditional.md), in the part that
made delegation unconditional inside one undertaking.

**Observed.** A Claude Code web session told to undertake an issue opened
another Claude Code web session to undertake the same issue. The first session
had already titled itself, established the task worktree and claimed the issue;
the second read the issue again, claimed it again, and wrote the code in a
context the first one could not see. Two sessions, one branch, one issue, and
the only thing bought with the second was a handoff.

## Why it could happen

`0017` read one failure — an orchestrator that swallowed a whole epic's wave
into its own context — and fixed it with a rule that reached further than the
failure did. `undertake`'s `Implement` was made to dispatch unconditionally,
so a session invoked on a single issue dispatched a second session for work
that was never going to run beside anything.

The constitution pointed the same way: *Plan first, then delegate the
implementation*, with nothing saying what delegation was for.

## Decided

**Delegation buys parallelism. Where there is no parallelism to buy, it buys a
second copy of the context already in hand.**

- **`embark` delegates, and that is unchanged.** An epic's wave is several task
  issues at once, and one session or subagent per task is what makes them
  concurrent. Every rule `0017` wrote there stands: the recorded model, the
  cheaper fallback default, the advisor, and the strong-model review that gates
  an implementor's pull request.
- **`undertake` does not delegate the body of the work.** The session that
  claimed the issue writes the code. It holds the claim, the branch, the pull
  request and the gates already, and a dispatch splits those from the hands
  doing the work for no gain.
- **The review round still delegates.** `review-cycle`'s `Verify the fix delta`
  dispatches a briefed subagent, and that is the one dispatch inside the
  sequence. The author of a delta cannot be an independent reader of it, so the
  second context there is the whole point.
- **`embark`-of-one keeps nothing.** A fleet of one was the case `0017` used to
  justify reaching into `undertake`; with the rule scoped to parallelism, there
  is nothing to carry over.

## Where it landed

`skills/undertake/SKILL.md` (`Implement`, and the two places that cited a
delegated implementor — `Claim the issue`'s clock and `The milestone`'s
provenance), the three `skills/undertake/references/{claude,omp,codex}.md`
route tables, which now record that there is no implementor route and why,
`skills/embark/SKILL.md` (`Non-goals`), `rules/constitution.md`
(*Delegation*), and `README.md`, whose constitution summary table carried a
copy of the sentence that changed. No step was renamed.
