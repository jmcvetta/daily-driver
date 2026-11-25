# The undertaker owns the issue — duplicate sessions buy nothing

**Status:** decided, 2026-09-17; partially superseded by note `0036`, 2026-11-25.
**Supersedes:** note `0017-delegation-is-unconditional` (retired to Git
history), in the part that made delegation unconditional inside one
undertaking.

**Observed.** A Claude Code web session told to undertake an issue opened
another Claude Code web session to undertake the same issue. The first session
had already titled itself, established the task worktree and claimed the issue;
the second read the issue again, claimed it again, and wrote the code in a
context the first one could not see. Two sessions, one branch, one issue, and
the only thing bought with the second was a handoff.

## Why it could happen

The delegation note read one failure — an orchestrator that swallowed a whole
epic's wave into its own context — and fixed it with a rule that reached
further than the failure did. `undertake`'s `Implement` was made to dispatch unconditionally,
so a session invoked on a single issue dispatched a second session for work
that was never going to run beside anything.

The constitution pointed the same way: *Plan first, then delegate the
implementation*, with nothing saying what delegation was for.

## Decided

**A second full undertaking is not justified by work that will not run in parallel.** A bounded component handoff can still reduce total cost when one routine worker replaces a long, settled implementation loop; note `0036` records that decision and its limits.

- **`embark` delegates, and that is unchanged.** An epic's wave is several task
  issues at once, and one session or subagent per task is what makes them
  concurrent. Every rule the delegation note wrote there stands: the recorded
model, the
  cheaper fallback default, the advisor, and the strong-model review that gates
  an implementor's pull request.
- **`undertake` does not start a second full undertaking for one issue.** The original observation remains valid: a second session repeats the claim and splits ownership of the branch, pull request and gates. The narrower rule that the owner must write all implementation code is superseded by note `0036`: the owner may delegate a bounded settled component slice while retaining the issue and outcome.
- **Review-round delegation remains independent review.** `Review the head` uses a full independent reviewer, and `Verify the fix delta` checks each correction batch independently. These review tasks are distinct from routine implementation handoffs in note `0036`; neither is removed or replaced by them. The author of a change cannot be its independent reader.
- **`embark`-of-one keeps nothing.** A fleet of one was the case the delegation
  note used to justify reaching into `undertake`; with the rule scoped to
  parallelism, there
  is nothing to carry over.

## Where it landed

`skills/undertake/SKILL.md` (`Implement`, and the two places that cited a
delegated implementor — `Claim the issue`'s clock and `The milestone`'s
provenance), the three `skills/undertake/references/{claude,omp,codex}.md`
route tables, which now record that there is no implementor route and why,
`skills/embark/SKILL.md` (`Non-goals`), `rules/constitution.md`
(*Delegation*), and `README.md`, whose constitution summary table carried a
copy of the sentence that changed. No step was renamed.
